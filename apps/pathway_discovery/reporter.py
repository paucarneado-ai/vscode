"""Generate audit reports in markdown and JSON."""

import json
import os
import time
from datetime import datetime

from apps.pathway_discovery.schemas import (
    FunctionRegistryEntry,
    InteractionTrace,
    ModuleDrift,
    ModuleRegistryEntry,
    PathwayRecommendation,
    PathwayRegistryEntry,
)

REPORT_SCHEMA_VERSION = 7  # V1.x intermediate role classification
BOOTSTRAP_MODULES = {"main", "__main__", "__init__"}

# Drift thresholds
FAN_OUT_NOTABLE = 5
FAN_OUT_CRITICAL = 8
FAN_IN_NOTABLE = 8
FAN_IN_CRITICAL = 12


def _is_bootstrap(module_id: str) -> bool:
    last = module_id.rsplit(".", 1)[-1] if "." in module_id else module_id
    return last in BOOTSTRAP_MODULES


def _bucket_counts(recs: list[PathwayRecommendation]) -> dict[str, int]:
    return {
        "candidates": len(recs),
        "immediate": sum(1 for r in recs if r.review_bucket == "immediate"),
        "known_debt": sum(1 for r in recs if r.review_bucket == "known_debt"),
        "backlog": sum(1 for r in recs if r.review_bucket == "backlog"),
        "watchlist": sum(1 for r in recs if r.review_bucket == "watchlist"),
        "ignored": sum(1 for r in recs if r.review_bucket == "ignore"),
        "prohibited_new": sum(1 for r in recs if r.governance_status == "PROHIBITED"),
    }


def _graph_health(modules: list[ModuleRegistryEntry]) -> dict[str, int]:
    if not modules:
        return {"max_fan_out_runtime": 0, "max_fan_in": 0, "protected_modules": 0}
    runtime = [m for m in modules if not _is_bootstrap(m.module_id)]
    return {
        "max_fan_out_runtime": max((m.fan_out for m in runtime), default=0),
        "max_fan_in": max(m.fan_in for m in modules),
        "protected_modules": sum(1 for m in modules if m.protected),
    }


def _module_snapshot(modules: list[ModuleRegistryEntry]) -> list[dict]:
    return [
        {"module_id": m.module_id, "fan_in": m.fan_in, "fan_out": m.fan_out,
         "protected": m.protected, "module_kind": m.module_kind}
        for m in modules
    ]


def _classify_drift(
    old_fo: int, new_fo: int, old_fi: int, new_fi: int,
) -> str:
    """Classify module drift severity."""
    fo_delta = abs(new_fo - old_fo)
    fi_delta = abs(new_fi - old_fi)
    if fo_delta == 0 and fi_delta == 0:
        return "stable"
    # Critical: crossed a critical threshold or large absolute change
    if (new_fo >= FAN_OUT_CRITICAL > old_fo) or (new_fi >= FAN_IN_CRITICAL > old_fi):
        return "critical_drift"
    if fo_delta >= 3 or fi_delta >= 4:
        return "critical_drift"
    # Notable: crossed a notable threshold or moderate change
    if (new_fo >= FAN_OUT_NOTABLE > old_fo) or (new_fi >= FAN_IN_NOTABLE > old_fi):
        return "notable_drift"
    if fo_delta >= 2 or fi_delta >= 2:
        return "notable_drift"
    return "mild_drift"


def compute_module_drifts(
    current: list[ModuleRegistryEntry],
    previous_snapshot: list[dict] | None,
) -> list[ModuleDrift]:
    if not previous_snapshot:
        return []
    prev_map = {m["module_id"]: m for m in previous_snapshot}
    drifts: list[ModuleDrift] = []
    for m in current:
        prev = prev_map.get(m.module_id)
        if not prev:
            drifts.append(ModuleDrift(
                module_id=m.module_id, fan_out_old=0, fan_out_new=m.fan_out,
                fan_in_old=0, fan_in_new=m.fan_in, classification="notable_drift",
            ))
            continue
        old_fo = prev.get("fan_out", 0)
        old_fi = prev.get("fan_in", 0)
        cls = _classify_drift(old_fo, m.fan_out, old_fi, m.fan_in)
        drifts.append(ModuleDrift(
            module_id=m.module_id, fan_out_old=old_fo, fan_out_new=m.fan_out,
            fan_in_old=old_fi, fan_in_new=m.fan_in, classification=cls,
        ))
    return drifts


def _delta_line(key: str, old_val: int | None, new_val: int) -> str:
    if old_val is None:
        return f"- {key}: {new_val} (new metric)"
    if old_val == new_val:
        return f"- {key}: {new_val} (unchanged)"
    return f"- {key}: {old_val} -> {new_val}"


def generate_report(
    recommendations: list[PathwayRecommendation],
    modules: list[ModuleRegistryEntry],
    functions: list[FunctionRegistryEntry],
    traces: list[InteractionTrace],
    pathways: list[PathwayRegistryEntry],
    previous_data: dict | None = None,
    module_drifts: list[ModuleDrift] | None = None,
    full_review_state: dict[str, dict] | None = None,
) -> str:
    lines: list[str] = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    counts = _bucket_counts(recommendations)
    health = _graph_health(modules)
    prev_summary = (previous_data or {}).get("summary", {})
    prev_health = (previous_data or {}).get("graph_health", {})
    drifts = module_drifts or []

    immediate = [r for r in recommendations if r.review_bucket == "immediate"]
    known_debt = [r for r in recommendations if r.review_bucket == "known_debt"]
    backlog = [r for r in recommendations if r.review_bucket == "backlog"]
    watchlist = [r for r in recommendations if r.review_bucket == "watchlist"]
    ignored = [r for r in recommendations if r.review_bucket == "ignore"]
    prohibited_new = [r for r in recommendations if r.governance_status == "PROHIBITED"]

    lines.append(f"# Pathway Audit Report — {now}")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append(f"- Modules: {len(modules)} | Functions: {len(functions)} | Traces: {len(traces)} | Pathways: {len(pathways)}")
    lines.append(f"- Candidates: {counts['candidates']} (immediate={counts['immediate']}, debt={counts['known_debt']}, backlog={counts['backlog']}, watchlist={counts['watchlist']}, ignored={counts['ignored']})")
    lines.append("")

    # Delta
    lines.append("## Delta vs Previous Audit")
    if prev_summary:
        for key in ("candidates", "known_debt", "backlog", "watchlist", "prohibited_new"):
            lines.append(_delta_line(key, prev_summary.get(key), counts[key]))
        for key in ("max_fan_out_runtime", "max_fan_in"):
            lines.append(_delta_line(key, prev_health.get(key), health.get(key, 0)))
    else:
        lines.append("No previous audit found.")
    lines.append("")

    # Module Drift
    lines.append("## Module Drift")
    notable = [d for d in drifts if d.classification in ("notable_drift", "critical_drift")]
    if notable:
        for d in notable:
            fo_s = f"fan_out {d.fan_out_old} -> {d.fan_out_new}" if d.fan_out_old != d.fan_out_new else ""
            fi_s = f"fan_in {d.fan_in_old} -> {d.fan_in_new}" if d.fan_in_old != d.fan_in_new else ""
            detail = ", ".join(x for x in [fo_s, fi_s] if x)
            lines.append(f"- **{d.module_id}** [{d.classification}]: {detail}")
    else:
        lines.append("No notable module drift detected.")
    lines.append("")

    # Immediate
    lines.append("## Immediate Review")
    _append_section(lines, immediate)

    # Known debt
    lines.append("## Known Debt")
    if known_debt:
        for r in known_debt:
            _append_rec(lines, r)
    else:
        lines.append("None.")
    lines.append("")

    # Backlog
    lines.append("## Backlog")
    _append_section(lines, backlog)

    # Watchlist
    lines.append("## Watchlist")
    if watchlist:
        lines.append("*Structurally interesting, downgraded by orchestrator signals.*")
        lines.append("")
        for r in watchlist:
            _append_rec(lines, r)
    else:
        lines.append("None.")
    lines.append("")

    # Ignored
    lines.append("## Ignored / Low-Confidence")
    if ignored:
        for r in ignored:
            lines.append(f"- **{r.recommendation_id}**: {r.candidate.description} [score={r.score}, conf={r.candidate.confidence}]")
    else:
        lines.append("None.")
    lines.append("")

    # Prohibited
    lines.append("## Prohibited Connections")
    if prohibited_new:
        for r in prohibited_new:
            _append_rec(lines, r)
    elif known_debt:
        lines.append("No new prohibited connections detected outside known debt.")
    else:
        lines.append("None detected. Architecture is clean.")
    lines.append("")

    # Graph health
    lines.append("## Graph Health")
    if modules:
        max_fo = max(m.fan_out for m in modules)
        max_fo_mod = next(m.module_id for m in modules if m.fan_out == max_fo)
        runtime = [m for m in modules if not _is_bootstrap(m.module_id)]
        rt_fo = max((m.fan_out for m in runtime), default=0) if runtime else 0
        rt_mod = next((m.module_id for m in runtime if m.fan_out == rt_fo), "n/a") if runtime else "n/a"
        lines.append(f"- Fan-out (all): {max_fo} ({max_fo_mod}) | (runtime): {rt_fo} ({rt_mod})")
        lines.append(f"- Fan-in max: {health['max_fan_in']} | Protected: {health['protected_modules']}")
    lines.append("")

    # Review Queue (active only: not resolved, not inactive)
    queue_items = [r for r in recommendations
                   if r.in_review_queue and r.operator_status != "resolved" and not r.inactive]
    if queue_items:
        lines.append("## Review Queue")
        lines.append("")
        for r in sorted(queue_items, key=lambda x: (-x.watchlist_severity_score, -x.debt_age, -x.score)):
            fp_short = r.candidate.stable_fingerprint[:8]
            if r.escalated_watchlist:
                tag = "[WATCHLIST-ESCALATED]"
            elif r.debt_status == "review_due":
                tag = "[KNOWN-DEBT-REVIEW-DUE]"
            else:
                tag = "[REVIEW-QUEUE]"
            lines.append(f"### {tag} {fp_short}")
            lines.append(f"- **Bucket:** {r.review_bucket} | **Severity:** {r.watchlist_severity_score} | **Debt age:** {r.debt_age}")
            lines.append(f"- **Why now:** {r.why_now}")
            lines.append(f"- **Hint:** {r.intervention_hint}")
            lines.append(f"- **Operator status:** {r.operator_status}")
            if r.operator_note:
                lines.append(f"- **Note:** {r.operator_note}")
            lines.append(f"- **Modules:** {', '.join(r.candidate.modules_involved)}")
            lines.append("")
    lines.append("")

    # Decision Log (reviewed, resolved, or inactive items)
    reviewed_items = [r for r in recommendations
                      if r.operator_status and r.operator_status != "unreviewed"]
    # Also include inactive historical entries from full_review_state if passed
    if reviewed_items or (full_review_state and any(
        e.get("operator_status", "unreviewed") != "unreviewed" or e.get("inactive")
        for e in full_review_state.values()
    )):
        lines.append("## Decision Log")
        lines.append("")
        # Active reviewed items
        for r in reviewed_items:
            fp_short = r.candidate.stable_fingerprint[:8]
            lines.append(f"- **{fp_short}** | status={r.operator_status} | bucket={r.review_bucket}")
            if r.decision_reason:
                lines.append(f"  reason: {r.decision_reason}")
            if r.operator_note:
                lines.append(f"  note: {r.operator_note}")
            if r.reviewed_at:
                lines.append(f"  reviewed: {r.reviewed_at}")
        # Inactive historical items from persisted state
        if full_review_state:
            active_fps = {r.candidate.stable_fingerprint for r in recommendations}
            for fp, entry in sorted(full_review_state.items()):
                if entry.get("inactive") and fp not in {r.candidate.stable_fingerprint for r in reviewed_items}:
                    lines.append(f"- **{fp[:8]}** | status={entry.get('operator_status', '?')} | **inactive**")
                    if entry.get("decision_reason"):
                        lines.append(f"  reason: {entry['decision_reason']}")
                    if entry.get("last_description"):
                        lines.append(f"  was: {entry['last_description'][:80]}")
        lines.append("")

    # Top 3 Actions
    lines.append("## Top 3 Actions")
    actionable = [r for r in recommendations if r.review_bucket in ("immediate", "backlog")]
    if actionable:
        for i, r in enumerate(actionable[:3], 1):
            lines.append(f"{i}. **{r.action}** -- {r.candidate.description} (score={r.score})")
    else:
        lines.append("No actionable recommendations.")
    lines.append("")

    # Top Structural Observations (when no actions)
    if not actionable:
        lines.append("## Top Structural Observations")
        # Prefer queue-backed items first
        observable = sorted(
            [r for r in recommendations if r.review_bucket in ("watchlist", "known_debt")],
            key=lambda r: (
                -(3 if r.in_review_queue else 0),
                -(2 if r.escalated_watchlist else (1 if r.review_bucket == "watchlist" else 0)),
                -r.watchlist_severity_score,
                -(r.debt_age if r.debt_status == "review_due" else 0),
                -r.score,
            ),
        )
        if observable:
            for i, r in enumerate(observable[:3], 1):
                if r.in_review_queue and r.escalated_watchlist:
                    tag = "[REVIEW-QUEUE] [WATCHLIST-ESCALATED]"
                elif r.in_review_queue:
                    tag = "[REVIEW-QUEUE]"
                elif r.escalated_watchlist:
                    tag = "[WATCHLIST-ESCALATED]"
                elif r.debt_status == "review_due":
                    tag = "[KNOWN-DEBT-REVIEW-DUE]"
                elif r.review_bucket == "watchlist":
                    tag = "[WATCHLIST]"
                else:
                    tag = "[KNOWN-DEBT]"
                extra = ""
                if r.watchlist_severity_score > 0:
                    extra = f" severity={r.watchlist_severity_score}"
                if r.debt_age > 0:
                    extra += f" debt_age={r.debt_age}"
                lines.append(f"{i}. {tag} {r.candidate.description} (score={r.score}{extra})")
        else:
            lines.append("No structural observations.")
        lines.append("")

    lines.append("## Known Limits")
    lines.append("- Direct imports and attribute calls only")
    lines.append("- Schema constructors suppressed; bootstrap excluded from runtime fan-out")
    lines.append("- Orchestrator intermediates → watchlist with severity scoring")
    lines.append("")

    return "\n".join(lines)


def _append_section(lines: list[str], recs: list[PathwayRecommendation]) -> None:
    if recs:
        for r in recs:
            _append_rec(lines, r)
    else:
        lines.append("None.")
    lines.append("")


def _append_rec(lines: list[str], r: PathwayRecommendation) -> None:
    lines.append(f"### {r.recommendation_id}: {r.candidate.candidate_type.value}")
    lines.append(f"- **Score:** {r.score} | **Priority:** {r.priority} | **Governance:** {r.governance_status}")

    conf_line = f"- **Confidence:** {r.candidate.confidence}"
    if r.candidate.orchestrator_penalty > 0:
        conf_line += f" (raw={r.candidate.raw_confidence}, penalty=-{r.candidate.orchestrator_penalty})"
    conf_line += f" — {r.candidate.confidence_reason}"
    lines.append(conf_line)

    lines.append(f"- **Occurrences:** {r.candidate.occurrence_count}")

    if r.candidate.intermediate_role and r.candidate.intermediate_role != "unknown":
        role_line = f"- **Intermediate role:** {r.candidate.intermediate_role} (conf={r.candidate.role_confidence})"
        if r.candidate.role_reason:
            role_line += f" -- {r.candidate.role_reason}"
        lines.append(role_line)

    if r.watchlist_age > 0:
        sev_info = f" | severity={r.watchlist_severity_score}" if r.watchlist_severity_score else ""
        age_line = f"- **Watchlist age:** {r.watchlist_age}{sev_info}"
        if r.escalated_watchlist:
            age_line += f" **[ESCALATED: {r.watchlist_escalation_reason}]**"
        lines.append(age_line)

    if r.debt_status:
        debt_line = f"- **Debt status:** {r.debt_status} (age={r.debt_age})"
        if r.debt_status == "review_due":
            debt_line += " **[review recommended]**"
        lines.append(debt_line)

    if r.candidate.depends_on_known_debt:
        lines.append(f"- **Depends on known debt:** {r.candidate.known_debt_reference}")
    lines.append(f"- **Description:** {r.candidate.description}")
    lines.append(f"- **Modules:** {', '.join(r.candidate.modules_involved)}")
    lines.append(f"- **Impact:** {r.candidate.impact_scope} | **Effort:** {r.candidate.estimated_effort} | **Risk:** {r.candidate.risk_level}")
    lines.append(f"- **Action:** {r.action}")
    if r.candidate.evidence:
        lines.append(f"- **Evidence** ({len(r.candidate.evidence)} sites):")
        for e in r.candidate.evidence[:5]:
            lines.append(f"  - `{e}`")
        if len(r.candidate.evidence) > 5:
            lines.append(f"  - ... and {len(r.candidate.evidence) - 5} more")
    lines.append("")


def generate_json(
    recommendations: list[PathwayRecommendation],
    modules: list[ModuleRegistryEntry],
    functions: list[FunctionRegistryEntry],
    traces: list[InteractionTrace],
    pathways: list[PathwayRegistryEntry],
    module_drifts: list[ModuleDrift] | None = None,
    full_review_state: dict[str, dict] | None = None,
) -> str:
    health = _graph_health(modules)
    counts = _bucket_counts(recommendations)
    drifts = module_drifts or []
    data = {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "modules": len(modules), "functions": len(functions),
            "traces": len(traces), "pathways": len(pathways),
            **counts,
            "candidate_types": dict(sorted(
                ((t, sum(1 for r in recommendations if r.candidate.candidate_type.value == t))
                 for t in set(r.candidate.candidate_type.value for r in recommendations)),
                key=lambda x: x[0],
            )) if recommendations else {},
        },
        "graph_health": {
            "max_fan_out_all": max((m.fan_out for m in modules), default=0),
            **health,
        },
        "module_snapshot": _module_snapshot(modules),
        "module_drift": [
            {"module_id": d.module_id, "fan_out_old": d.fan_out_old, "fan_out_new": d.fan_out_new,
             "fan_in_old": d.fan_in_old, "fan_in_new": d.fan_in_new, "classification": d.classification}
            for d in drifts
        ],
        "watchlist_state": {
            r.candidate.stable_fingerprint: r.watchlist_age
            for r in recommendations if r.review_bucket == "watchlist"
        },
        "debt_state": {
            r.candidate.stable_fingerprint: r.debt_age
            for r in recommendations if r.debt_status
        },
        "review_queue_state": full_review_state or {
            r.candidate.stable_fingerprint: {
                "operator_status": r.operator_status,
                "operator_note": r.operator_note,
                "reviewed_at": r.reviewed_at,
                "decision_reason": r.decision_reason,
                "inactive": r.inactive,
                "last_bucket": r.review_bucket,
                "last_description": r.candidate.description[:100],
            }
            for r in recommendations if r.in_review_queue
        },
        "recommendations": [
            {
                "id": r.recommendation_id,
                "stable_fingerprint": r.candidate.stable_fingerprint,
                "type": r.candidate.candidate_type.value,
                "score": r.score,
                "priority": r.priority,
                "review_bucket": r.review_bucket,
                "governance": r.governance_status,
                "action": r.action,
                "modules": r.candidate.modules_involved,
                "confidence": r.candidate.confidence,
                "occurrence_count": r.candidate.occurrence_count,
                "watchlist_age": r.watchlist_age,
                "watchlist_severity_score": r.watchlist_severity_score,
                "escalated_watchlist": r.escalated_watchlist,
                "debt_status": r.debt_status,
                "debt_age": r.debt_age,
                "in_review_queue": r.in_review_queue,
                "operator_status": r.operator_status,
                "operator_note": r.operator_note,
                "reviewed_at": r.reviewed_at,
                "decision_reason": r.decision_reason,
                "inactive": r.inactive,
                "why_now": r.why_now,
                "intervention_hint": r.intervention_hint,
                "intermediate_role": r.candidate.intermediate_role,
                "role_confidence": r.candidate.role_confidence,
                "role_reason": r.candidate.role_reason,
                "depends_on_known_debt": r.candidate.depends_on_known_debt,
                "evidence": r.candidate.evidence[:5],
            }
            for r in recommendations
        ],
    }
    return json.dumps(data, indent=2, ensure_ascii=False)


def _load_previous_data(repo_root: str) -> dict | None:
    path = os.path.join(repo_root, "reports", "pathway_audit_latest.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, KeyError):
        return None


def _persist_reports(md: str, js: str, repo_root: str) -> tuple[str, str]:
    reports_dir = os.path.join(repo_root, "reports")
    os.makedirs(reports_dir, exist_ok=True)
    md_path = os.path.join(reports_dir, "pathway_audit_latest.md")
    json_path = os.path.join(reports_dir, "pathway_audit_latest.json")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    with open(json_path, "w", encoding="utf-8") as f:
        f.write(js)
    return md_path, json_path


def run_audit(root_path: str | None = None) -> None:
    from apps.pathway_discovery.analyzer import analyze_interactions
    from apps.pathway_discovery.heuristics import (
        detect_long_paths, detect_prohibited_connections,
        detect_redundant_transforms, get_prohibited_pairs,
    )
    from apps.pathway_discovery.registry import build_registry
    from apps.pathway_discovery.scorer import score_candidates, merge_review_state

    if root_path is None:
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        root_path = os.path.join(repo_root, "apps")
    else:
        repo_root = os.path.dirname(root_path)

    t0 = time.time()

    modules, functions, pathways = build_registry(root_path)
    traces = analyze_interactions(root_path)

    prohibited_candidates = detect_prohibited_connections(traces)
    prohibited_pairs = get_prohibited_pairs(traces)
    redundant_candidates = detect_redundant_transforms(traces, prohibited_pairs=prohibited_pairs)
    long_path_candidates = detect_long_paths(pathways, traces, modules=modules)
    candidates = prohibited_candidates + redundant_candidates + long_path_candidates

    previous_data = _load_previous_data(repo_root)
    prev_wl = (previous_data or {}).get("watchlist_state", {})
    prev_debt = (previous_data or {}).get("debt_state", {})
    prev_rq = (previous_data or {}).get("review_queue_state", {})
    prev_snapshot = (previous_data or {}).get("module_snapshot")

    drifts = compute_module_drifts(modules, prev_snapshot)
    drift_map = {d.module_id: d for d in drifts}

    recommendations = score_candidates(
        candidates, previous_watchlist=prev_wl, previous_debt=prev_debt,
        module_drifts=drift_map, previous_review_queue=prev_rq,
    )

    # Merge review state: active + inactive historical
    full_rq = merge_review_state(recommendations, prev_rq)

    elapsed = time.time() - t0

    md = generate_report(recommendations, modules, functions, traces, pathways, previous_data, drifts, full_rq)
    js = generate_json(recommendations, modules, functions, traces, pathways, drifts, full_rq)
    md_path, json_path = _persist_reports(md, js, repo_root)

    import sys
    out = md.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(sys.stdout.encoding or "utf-8", errors="replace")
    print(out)
    print(f"---\nAudit completed in {elapsed:.2f}s")
    print(f"Persisted: {md_path}")
    print(f"Persisted: {json_path}")


if __name__ == "__main__":
    run_audit()
