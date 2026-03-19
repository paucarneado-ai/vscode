"""Score candidate pathways and classify priority/governance."""

import hashlib

from apps.pathway_discovery.schemas import (
    CandidatePathway,
    CandidateType,
    ModuleDrift,
    PathwayRecommendation,
)

WEIGHTS = {
    "frequency": 0.15, "token_saving": 0.10, "latency_saving": 0.10,
    "error_reduction": 0.15, "reusability": 0.15, "confidence": 0.15,
    "effort": 0.10, "risk": 0.10,
}
FREQ_SCORES = {"per_request": 100, "periodic": 50, "rare": 10, "unknown": 30}
ERROR_REDUCTION_BY_TYPE = {
    CandidateType.REDUNDANT_TRANSFORM: 60, CandidateType.DUPLICATE_LOGIC: 70,
    CandidateType.GENERIC_CONTRACT: 40, CandidateType.LONG_PATH: 30,
    CandidateType.SHARED_FUNCTION: 50, CandidateType.DIRECT_PATH: 30,
    CandidateType.PROHIBITED_CONNECTION: 90,
}
EFFORT_SCORES = {"small": 90, "medium": 50, "large": 20}
RISK_SCORES = {"low": 100, "medium": 60, "high": 30, "critical": 10}
RISK_SEVERITY = {"low": 0, "medium": 15, "high": 30, "critical": 50}

WATCHLIST_ESCALATION_THRESHOLD = 60


def compute_fingerprint(c: CandidatePathway) -> str:
    parts = [c.candidate_type.value, "|".join(sorted(c.modules_involved))]
    if c.known_debt_reference:
        parts.append(c.known_debt_reference)
    return hashlib.sha256("::".join(parts).encode()).hexdigest()[:16]


def compute_watchlist_severity(
    score: float,
    age: int,
    c: CandidatePathway,
    module_drifts: dict[str, ModuleDrift] | None = None,
) -> tuple[float, str]:
    """Compute 0-100 severity for a watchlist item. Returns (severity, reason)."""
    parts: list[str] = []
    severity = 0.0

    # Base: candidate score contributes 0-40
    base = min(score * 0.4, 40)
    severity += base
    parts.append(f"base_score={base:.0f}")

    # Age: each audit adds 8, capped at 24
    age_contrib = min(age * 8, 24)
    severity += age_contrib
    if age > 1:
        parts.append(f"age={age}(+{age_contrib:.0f})")

    # Protected: +15
    if c.touches_protected:
        severity += 15
        parts.append("touches_protected(+15)")

    # Depends on known debt: +8
    if c.depends_on_known_debt:
        severity += 8
        parts.append("depends_on_debt(+8)")

    # Risk level
    risk_add = RISK_SEVERITY.get(c.risk_level, 0)
    if risk_add:
        severity += risk_add
        parts.append(f"risk={c.risk_level}(+{risk_add})")

    # Module drift of involved modules
    if module_drifts:
        drift_bonus = 0
        for mid in c.modules_involved:
            d = module_drifts.get(mid)
            if d and d.classification in ("notable_drift", "critical_drift"):
                drift_bonus += 10 if d.classification == "notable_drift" else 20
        if drift_bonus:
            severity += drift_bonus
            parts.append(f"module_drift(+{drift_bonus})")

    # Role-based adjustment: composition hubs and translators are less alarming
    if c.intermediate_role == "shared_composer":
        role_reduction = min(severity * 0.35, 25)  # Reduce up to 35%, max 25 points
        severity -= role_reduction
        parts.append(f"shared_composer(-{role_reduction:.0f})")
    elif c.intermediate_role == "contract_translator":
        role_reduction = min(severity * 0.45, 30)
        severity -= role_reduction
        parts.append(f"contract_translator(-{role_reduction:.0f})")

    return round(min(max(severity, 0), 100), 1), "; ".join(parts)


def _classify_priority(score: float, confidence: float) -> str:
    if confidence < 0.5:
        return "low"
    if score >= 70:
        return "high"
    if score >= 45:
        return "medium"
    if score >= 20:
        return "low"
    return "skip"


def _classify_bucket(priority: str, candidate: CandidatePathway, governance: str) -> str:
    if governance == "KNOWN_DEBT":
        return "known_debt"
    if candidate.candidate_type == CandidateType.PROHIBITED_CONNECTION:
        return "immediate"
    if priority == "high":
        return "immediate"
    if priority == "medium":
        return "backlog"
    if (candidate.candidate_type == CandidateType.LONG_PATH
            and candidate.orchestrator_penalty > 0
            and candidate.confidence < 0.5
            and candidate.confidence + candidate.orchestrator_penalty >= 0.5):
        raw_score = sum(_raw_breakdown(candidate)[k] * WEIGHTS[k] for k in WEIGHTS)
        if raw_score >= 40:
            return "watchlist"
    return "ignore"


def _raw_breakdown(c: CandidatePathway) -> dict[str, float]:
    return {
        "frequency": FREQ_SCORES.get(c.call_frequency, 30),
        "token_saving": min(c.estimated_token_saving / 5, 100) if c.estimated_token_saving else 0,
        "latency_saving": min(c.estimated_latency_saving_ms * 2, 100),
        "error_reduction": ERROR_REDUCTION_BY_TYPE.get(c.candidate_type, 0),
        "reusability": min(len(c.modules_involved) * 25, 100),
        "confidence": c.raw_confidence * 100,
        "effort": EFFORT_SCORES.get(c.estimated_effort, 50),
        "risk": RISK_SCORES.get(c.risk_level, 50),
    }


def _classify_governance(candidate: CandidatePathway, priority: str) -> str:
    if candidate.candidate_type == CandidateType.PROHIBITED_CONNECTION:
        if "KNOWN DEBT" in candidate.description:
            return "KNOWN_DEBT"
        return "PROHIBITED"
    if candidate.touches_protected or candidate.risk_level in ("high", "critical"):
        return "NEEDS_HUMAN"
    if candidate.confidence < 0.5:
        return "DEFERRED"
    if priority in ("high", "medium") and candidate.estimated_effort == "small" and not candidate.touches_protected:
        return "RECOMMENDED_FOR_AUTO_APPROVAL"
    return "NEEDS_HUMAN"


def _classify_action(candidate: CandidatePathway) -> str:
    actions = {
        CandidateType.REDUNDANT_TRANSFORM: "extract_shared_function",
        CandidateType.LONG_PATH: "evaluate_direct_path",
        CandidateType.PROHIBITED_CONNECTION: "fix_architecture_violation",
        CandidateType.SHARED_FUNCTION: "extract_shared_function",
        CandidateType.GENERIC_CONTRACT: "narrow_contract",
        CandidateType.DUPLICATE_LOGIC: "consolidate",
        CandidateType.DIRECT_PATH: "add_direct_path",
    }
    return actions.get(candidate.candidate_type, "review")


def _generate_why_now(r_bucket: str, escalated: bool, severity: float, age: int,
                      debt_status: str, debt_age: int, c: CandidatePathway) -> str:
    parts: list[str] = []
    if escalated:
        parts.append(f"persistent {age} audits")
        if c.touches_protected:
            parts.append("touches protected module")
        if c.depends_on_known_debt:
            parts.append("depends on known debt")
        parts.append(f"severity={severity}")
    elif debt_status == "review_due":
        parts.append(f"known debt active for {debt_age} audits")
        parts.append("review threshold reached")
    return ", ".join(parts) if parts else ""


def _generate_intervention_hint(c: CandidatePathway, debt_status: str) -> str:
    if debt_status == "review_due":
        mods = " -> ".join(c.modules_involved[:2])
        return f"Review service-layer extraction around {mods}"
    if c.candidate_type == CandidateType.LONG_PATH:
        mid = c.modules_involved[1] if len(c.modules_involved) >= 2 else "intermediate"
        return f"Evaluate if {mid} orchestration can be simplified or if direct paths are viable"
    return "Review structural finding for actionability"


def score_candidates(
    candidates: list[CandidatePathway],
    previous_watchlist: dict[str, int] | None = None,
    previous_debt: dict[str, int] | None = None,
    module_drifts: dict[str, ModuleDrift] | None = None,
    previous_review_queue: dict[str, dict] | None = None,
) -> list[PathwayRecommendation]:
    recommendations: list[PathwayRecommendation] = []
    prev_wl = previous_watchlist or {}
    prev_debt = previous_debt or {}
    prev_rq = previous_review_queue or {}

    for i, c in enumerate(candidates, 1):
        c.stable_fingerprint = compute_fingerprint(c)

        breakdown = {
            "frequency": FREQ_SCORES.get(c.call_frequency, 30),
            "token_saving": min(c.estimated_token_saving / 5, 100) if c.estimated_token_saving else 0,
            "latency_saving": min(c.estimated_latency_saving_ms * 2, 100),
            "error_reduction": ERROR_REDUCTION_BY_TYPE.get(c.candidate_type, 0),
            "reusability": min(len(c.modules_involved) * 25, 100),
            "confidence": c.confidence * 100,
            "effort": EFFORT_SCORES.get(c.estimated_effort, 50),
            "risk": RISK_SCORES.get(c.risk_level, 50),
        }

        score = round(min(max(sum(breakdown[k] * WEIGHTS[k] for k in WEIGHTS), 0), 100), 1)

        raw_bd = _raw_breakdown(c)
        raw_score = round(sum(raw_bd[k] * WEIGHTS[k] for k in WEIGHTS), 1)
        breakdown.update({
            "raw_confidence": round(c.raw_confidence * 100, 1),
            "orchestrator_penalty": round(c.orchestrator_penalty * 100, 1),
            "final_confidence": round(c.confidence * 100, 1),
            "raw_score": raw_score,
            "final_score": score,
            "intermediate_role": c.intermediate_role,
            "role_confidence": round(c.role_confidence * 100, 1),
        })

        priority = _classify_priority(score, c.confidence)
        governance = _classify_governance(c, priority)
        bucket = _classify_bucket(priority, c, governance)
        action = _classify_action(c)

        # Watchlist aging
        fp = c.stable_fingerprint
        seen_prev = fp in prev_wl
        age = (prev_wl[fp] + 1) if seen_prev else (1 if bucket == "watchlist" else 0)

        # Watchlist severity
        severity = 0.0
        severity_reason = ""
        escalated = False
        if bucket == "watchlist":
            severity, severity_reason = compute_watchlist_severity(score, age, c, module_drifts)
            escalated = severity >= WATCHLIST_ESCALATION_THRESHOLD

        # Known debt lifecycle
        debt_status = ""
        debt_age = 0
        if governance == "KNOWN_DEBT":
            debt_age = prev_debt.get(fp, 0) + 1
            debt_status = "review_due" if debt_age >= 5 else "active"

        # Review queue
        in_queue = escalated or debt_status == "review_due"
        prev_rq_entry = prev_rq.get(fp, {})
        # Preserve operator fields from previous state
        op_status = prev_rq_entry.get("operator_status", "unreviewed") if in_queue else ""
        op_note = prev_rq_entry.get("operator_note", "") if in_queue else ""
        reviewed_at = prev_rq_entry.get("reviewed_at", "") if in_queue else ""
        decision_reason = prev_rq_entry.get("decision_reason", "") if in_queue else ""
        # Don't put resolved items back in active queue
        if op_status == "resolved":
            in_queue = False
        why = _generate_why_now(bucket, escalated, severity, age, debt_status, debt_age, c) if in_queue else ""
        hint = _generate_intervention_hint(c, debt_status) if in_queue else ""

        recommendations.append(
            PathwayRecommendation(
                recommendation_id=f"PR-{i:03d}",
                candidate=c,
                score=score,
                score_breakdown={k: (round(v, 1) if isinstance(v, (int, float)) else v) for k, v in breakdown.items()},
                priority=priority,
                review_bucket=bucket,
                governance_status=governance,
                action=action,
                rationale=c.description,
                seen_in_previous_audit=seen_prev,
                watchlist_age=age,
                escalated_watchlist=escalated,
                watchlist_severity_score=severity,
                watchlist_escalation_reason=severity_reason if escalated else "",
                debt_status=debt_status,
                debt_age=debt_age,
                in_review_queue=in_queue,
                operator_status=op_status,
                operator_note=op_note,
                why_now=why,
                intervention_hint=hint,
                reviewed_at=reviewed_at,
                decision_reason=decision_reason,
                inactive=False,
            )
        )

    recommendations.sort(key=lambda r: r.score, reverse=True)
    return recommendations


def merge_review_state(
    recommendations: list[PathwayRecommendation],
    previous_review_queue: dict[str, dict],
) -> dict[str, dict]:
    """Merge current recommendations with previous review state.

    Returns the full review_queue_state for persistence:
    - Active items from current findings
    - Inactive items that disappeared but were previously tracked
    - Revived items that reappeared
    """
    current_fps = {r.candidate.stable_fingerprint for r in recommendations if r.in_review_queue}
    result: dict[str, dict] = {}

    # Current active items
    for r in recommendations:
        fp = r.candidate.stable_fingerprint
        if r.in_review_queue:
            result[fp] = {
                "operator_status": r.operator_status,
                "operator_note": r.operator_note,
                "reviewed_at": r.reviewed_at,
                "decision_reason": r.decision_reason,
                "inactive": False,
                "last_bucket": r.review_bucket,
                "last_description": r.candidate.description[:100],
            }

    # Previously tracked items that no longer appear
    for fp, prev_entry in previous_review_queue.items():
        if fp not in current_fps and fp not in result:
            entry = dict(prev_entry)
            entry["inactive"] = True
            result[fp] = entry

    return result


