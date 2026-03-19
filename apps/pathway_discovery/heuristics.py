"""Heuristic detection rules for pathway candidates."""

from collections import defaultdict

from apps.pathway_discovery.schemas import (
    CandidatePathway,
    CandidateType,
    InteractionTrace,
    PathwayRegistryEntry,
)

# Patterns that should never exist in the codebase.
PROHIBITED_PATTERNS: dict[tuple[str, str], str] = {
    ("routes", "db"): "Routes should not access DB directly; use service layer",
    ("services", "routes"): "Services should not import from routes (circular risk)",
}

# Known architectural debt — accepted patterns that are not actionable now.
# Empty after service-layer extraction resolved routes.leads -> db debt.
KNOWN_DEBT: dict[tuple[str, str], str] = {}

_candidate_counter = 0


def _next_id() -> str:
    global _candidate_counter
    _candidate_counter += 1
    return f"CP-{_candidate_counter:03d}"


def _is_known_debt(source: str, target: str) -> tuple[bool, str]:
    """Check if a source->target pair matches known debt."""
    for (src_pat, tgt_pat), reason in KNOWN_DEBT.items():
        if src_pat in source and tgt_pat in target:
            return True, reason
    return False, ""


_ORCHESTRATOR_SIGNALS = {"route", "handler", "endpoint", "controller", "view"}


def _estimate_orchestrator_penalty(
    intermediate: str,
    b_fan_out: int,
    b_to_c_traces: list[InteractionTrace],
) -> tuple[float, str]:
    """Return (confidence_penalty 0.0-0.3, reason) if intermediate looks like a legitimate orchestrator."""
    penalty = 0.0
    reasons: list[str] = []

    # Signal 1: intermediate is a route module (routes naturally call multiple services)
    if "route" in intermediate.lower():
        penalty += 0.1
        reasons.append("intermediate is a route module")

    # Signal 2: high fan-out suggests orchestration role
    if b_fan_out >= 4:
        penalty += 0.1
        reasons.append(f"fan-out={b_fan_out} suggests orchestrator")

    # Signal 3: intermediate calls multiple distinct downstream modules
    downstream_modules = {t.callee_module for t in b_to_c_traces if t.callee_module}
    if len(downstream_modules) >= 3:
        penalty += 0.1
        reasons.append(f"calls {len(downstream_modules)} distinct downstream modules")

    return min(penalty, 0.3), "; ".join(reasons) if reasons else ""


def _classify_intermediate_role(
    intermediate: str,
    all_b_traces: list[InteractionTrace],
    a_to_b_traces: list[InteractionTrace],
) -> tuple[str, float, str]:
    """Classify the role of an intermediate module in a long path.

    Returns (role, confidence, reason).
    Signals:
      shared_composer: calls >=3 distinct external modules, constructs output
      contract_translator: receives one contract type, builds another, delegates to a single core function
      pass_through: minimal transformation, mostly forwarding
      unknown: insufficient evidence
    """
    # Distinct external modules called by the intermediate
    downstream_modules = {t.callee_module for t in all_b_traces if t.callee_module and t.callee_module != intermediate}
    # Distinct functions called
    downstream_funcs = {t.callee_function for t in all_b_traces if t.callee_module and t.callee_module != intermediate}
    # How many distinct callers use this intermediate (consumers / reuse signal)
    upstream_callers = {t.caller_module for t in a_to_b_traces}

    reasons: list[str] = []

    # --- shared_composer ---
    # Calls >=3 distinct external modules AND has evidence of schema/contract construction
    schema_construction = any(
        f[0].isupper() or "build_" in f or "get_" in f or "determine_" in f
        for f in downstream_funcs
    )
    if len(downstream_modules) >= 3 and schema_construction:
        reasons.append(f"calls {len(downstream_modules)} external modules")
        reasons.append(f"invokes {len(downstream_funcs)} distinct functions including composition")
        if len(upstream_callers) >= 2:
            reasons.append(f"reused by {len(upstream_callers)} upstream callers")
        conf = 0.85 if len(upstream_callers) >= 2 else 0.7
        return "shared_composer", conf, "; ".join(reasons)

    # --- contract_translator ---
    # Calls exactly 1-2 external modules, one of which is a core internal function
    # AND the intermediate is in a route/intake context
    if len(downstream_modules) <= 2 and len(downstream_funcs) <= 3:
        has_internal_delegation = any("_internal" in f or "create" in f.lower() for f in downstream_funcs)
        is_intake_context = "intake" in intermediate.lower() or "webhook" in intermediate.lower()
        if has_internal_delegation or is_intake_context:
            reasons.append(f"delegates to {len(downstream_funcs)} functions via {len(downstream_modules)} modules")
            reasons.append("translates/normalizes payload before core delegation")
            return "contract_translator", 0.7, "; ".join(reasons)

    # --- pass_through ---
    # Very few downstream calls, low diversity — likely just forwarding
    if len(downstream_modules) <= 1 and len(downstream_funcs) <= 2:
        reasons.append(f"only {len(downstream_funcs)} downstream calls to {len(downstream_modules)} module")
        reasons.append("minimal transformation evidence")
        return "pass_through", 0.6, "; ".join(reasons)

    return "unknown", 0.3, "insufficient evidence to classify intermediate role"


def detect_long_paths(
    pathways: list[PathwayRegistryEntry],
    traces: list[InteractionTrace],
    modules: list | None = None,
) -> list[CandidatePathway]:
    """Detect module chains with 3+ hops where a shorter path might exist.

    If modules is provided, uses fan-out data for orchestrator detection.
    Classifies intermediate role to avoid false positives on composition hubs.
    """
    candidates: list[CandidatePathway] = []

    # Build adjacency + fan-out lookup
    graph: dict[str, set[str]] = defaultdict(set)
    for pw in pathways:
        graph[pw.source_module].add(pw.target_module)

    fan_out_map: dict[str, int] = {}
    if modules:
        for m in modules:
            fan_out_map[m.module_id] = m.fan_out

    for a, a_targets in graph.items():
        for b in a_targets:
            for c in graph.get(b, set()):
                if c != a and c not in a_targets:
                    a_to_b_traces = [
                        t for t in traces
                        if t.caller_module == a and t.callee_module == b and t.confidence >= 0.7
                    ]
                    b_to_c_traces = [
                        t for t in traces
                        if t.caller_module == b and t.callee_module == c and t.confidence >= 0.7
                    ]
                    if a_to_b_traces and b_to_c_traces:
                        base_conf = min(
                            min(t.confidence for t in a_to_b_traces),
                            min(t.confidence for t in b_to_c_traces),
                        )

                        # Orchestrator penalty
                        b_fo = fan_out_map.get(b, len(graph.get(b, set())))
                        # Gather ALL traces from b for downstream diversity check
                        all_b_traces = [t for t in traces if t.caller_module == b and t.confidence >= 0.7]
                        penalty, orch_reason = _estimate_orchestrator_penalty(b, b_fo, all_b_traces)
                        conf = round(max(base_conf - penalty, 0.3), 2)

                        conf_parts = [f"base={base_conf:.2f} from {len(a_to_b_traces)}+{len(b_to_c_traces)} traces"]
                        if penalty > 0:
                            conf_parts.append(f"penalty=-{penalty:.1f} ({orch_reason})")

                        # Known debt dependency
                        is_debt_bc, debt_reason = _is_known_debt(b, c)
                        is_debt_ab, _ = _is_known_debt(a, b)
                        depends_debt = is_debt_bc or is_debt_ab
                        debt_ref = f"{b}->{c}" if is_debt_bc else (f"{a}->{b}" if is_debt_ab else "")

                        # Classify intermediate role
                        role, role_conf, role_reason = _classify_intermediate_role(
                            b, all_b_traces, a_to_b_traces,
                        )

                        short_b = b.split(".")[-1]
                        if role == "shared_composer":
                            desc = (
                                f"Chain {a} -> {b} -> {c}: "
                                f"{short_b} is a shared composition hub; "
                                f"persistent structural pattern, not confirmed pass-through"
                            )
                        elif role == "contract_translator":
                            desc = (
                                f"Chain {a} -> {b} -> {c}: "
                                f"{short_b} translates contracts between surfaces; "
                                f"review only if translation logic becomes stale"
                            )
                        else:
                            desc = (
                                f"Chain {a} -> {b} -> {c}: "
                                f"possible pass-through at {short_b}; "
                                f"manual semantic review required"
                            )
                        if penalty > 0:
                            desc += f" (orchestrator signals: {orch_reason})"

                        candidates.append(
                            CandidatePathway(
                                candidate_id=_next_id(),
                                candidate_type=CandidateType.LONG_PATH,
                                description=desc,
                                modules_involved=[a, b, c],
                                evidence=[
                                    f"{t.file_path}:{t.line_number} {t.caller_function}->{t.callee_function}"
                                    for t in a_to_b_traces[:2] + b_to_c_traces[:2]
                                ],
                                current_hops=2,
                                proposed_hops=1,
                                call_frequency="per_request" if "route" in a.lower() else "unknown",
                                confidence=conf,
                                raw_confidence=base_conf,
                                orchestrator_penalty=round(penalty, 2),
                                confidence_reason="; ".join(conf_parts),
                                impact_scope="structural",
                                estimated_effort="medium",
                                risk_level="medium" if any(
                                    t.callee_module and "scoring" in t.callee_module for t in b_to_c_traces
                                ) else "low",
                                touches_protected=any(
                                    "scoring" in m or "db" in m or "auth" in m for m in [a, b, c]
                                ),
                                depends_on_known_debt=depends_debt,
                                known_debt_reference=debt_ref,
                                intermediate_role=role,
                                role_confidence=role_conf,
                                role_reason=role_reason,
                            )
                        )

    return candidates


# Schema constructor suffixes — repeated construction is normal, not redundancy
_SCHEMA_CONSTRUCTOR_SUFFIXES = ("Response", "Create", "Payload", "Schema", "Result", "Entry")


def _is_schema_constructor(callee_module: str | None, callee_function: str) -> bool:
    """Return True if the call is likely a schema/model constructor."""
    if callee_module and "schema" in callee_module.lower():
        return True
    return any(callee_function.endswith(suffix) for suffix in _SCHEMA_CONSTRUCTOR_SUFFIXES)


# Infrastructure calls that are normal when repeated within a service module
_INFRA_CALL_NAMES = {"get_db"}


def _is_normal_infra_call(callee_module: str | None, callee_function: str,
                          caller_modules: set[str]) -> bool:
    """Return True if repeated calls are normal service-layer infrastructure access."""
    if callee_function not in _INFRA_CALL_NAMES:
        return False
    # Only suppress when all callers are services (not routes accessing db directly)
    return all("services" in m for m in caller_modules)


def detect_redundant_transforms(
    traces: list[InteractionTrace],
    prohibited_pairs: set[tuple[str, str]] | None = None,
) -> list[CandidatePathway]:
    """Detect the same function called from 3+ distinct call sites.

    Suppresses:
    - Calls already covered by prohibited connections
    - Schema constructor calls (normal contract construction, not real redundancy)
    """
    candidates: list[CandidatePathway] = []
    suppressed = prohibited_pairs or set()

    call_sites: dict[tuple[str | None, str], list[InteractionTrace]] = defaultdict(list)
    for t in traces:
        if t.confidence >= 0.7 and t.callee_module:
            key = (t.callee_module, t.callee_function)
            call_sites[key].append(t)

    for (mod, func), site_traces in call_sites.items():
        unique_callers = {t.caller_function for t in site_traces}
        if len(unique_callers) >= 3:
            # Suppress if already covered by prohibited pattern
            caller_modules = {t.caller_module for t in site_traces}
            if mod and all((cm, mod) in suppressed for cm in caller_modules):
                continue

            # Suppress schema constructors — repeated instantiation is normal
            if _is_schema_constructor(mod, func):
                continue

            # Suppress normal infra calls within service layer
            if _is_normal_infra_call(mod, func, caller_modules):
                continue

            avg_conf = sum(t.confidence for t in site_traces) / len(site_traces)
            candidates.append(
                CandidatePathway(
                    candidate_id=_next_id(),
                    candidate_type=CandidateType.REDUNDANT_TRANSFORM,
                    description=f"{mod}.{func} called from {len(unique_callers)} distinct functions",
                    modules_involved=list(caller_modules | {mod}),
                    evidence=[
                        f"{t.file_path}:{t.line_number} {t.caller_function}() -> {func}()"
                        for t in site_traces[:5]
                    ],
                    current_hops=len(unique_callers),
                    proposed_hops=1,
                    call_frequency="per_request",
                    confidence=round(avg_conf, 2),
                    confidence_reason=f"avg confidence {avg_conf:.2f} across {len(site_traces)} traces",
                    impact_scope="local",
                    estimated_effort="small",
                    risk_level="low",
                    touches_protected=mod is not None and any(
                        kw in mod for kw in ("scoring", "db", "auth")
                    ),
                    occurrence_count=len(site_traces),
                )
            )

    return candidates


def detect_prohibited_connections(
    traces: list[InteractionTrace],
) -> list[CandidatePathway]:
    """Flag prohibited patterns, consolidated per unique source->target pair."""
    # Group matching traces by (source_module, target_module, pattern_reason)
    groups: dict[tuple[str, str, str], list[InteractionTrace]] = defaultdict(list)

    for t in traces:
        if t.callee_module is None or t.confidence < 0.5:
            continue
        for (src_pat, tgt_pat), reason in PROHIBITED_PATTERNS.items():
            if src_pat in t.caller_module.lower() and tgt_pat in t.callee_module.lower():
                key = (t.caller_module, t.callee_module, reason)
                groups[key].append(t)

    candidates: list[CandidatePathway] = []
    for (src, tgt, reason), group_traces in groups.items():
        is_debt, debt_reason = _is_known_debt(src, tgt)
        evidence = [
            f"{t.file_path}:{t.line_number} {t.caller_function}() -> {t.callee_function}()"
            for t in group_traces
        ]
        avg_conf = sum(t.confidence for t in group_traces) / len(group_traces)

        desc = f"Prohibited: {src} -> {tgt} ({reason})"
        if is_debt:
            desc += f" [KNOWN DEBT: {debt_reason}]"

        candidates.append(
            CandidatePathway(
                candidate_id=_next_id(),
                candidate_type=CandidateType.PROHIBITED_CONNECTION,
                description=desc,
                modules_involved=[src, tgt],
                evidence=evidence,
                confidence=round(avg_conf, 2),
                confidence_reason=f"consolidated from {len(group_traces)} call sites",
                impact_scope="architectural",
                estimated_effort="medium" if not is_debt else "large",
                risk_level="critical" if not is_debt else "medium",
                touches_protected=True,
                occurrence_count=len(group_traces),
            )
        )

    return candidates


def get_prohibited_pairs(traces: list[InteractionTrace]) -> set[tuple[str, str]]:
    """Return set of (caller_module, callee_module) pairs that match prohibited patterns.
    Used by detect_redundant_transforms to suppress overlapping findings."""
    pairs: set[tuple[str, str]] = set()
    for t in traces:
        if t.callee_module is None or t.confidence < 0.5:
            continue
        for (src_pat, tgt_pat), _ in PROHIBITED_PATTERNS.items():
            if src_pat in t.caller_module.lower() and tgt_pat in t.callee_module.lower():
                pairs.add((t.caller_module, t.callee_module))
    return pairs
