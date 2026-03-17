import csv
import io
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from starlette.responses import PlainTextResponse

from apps.api.db import get_db
from apps.api.events import emit_event
from apps.api.routes.leads import _get_actionable_leads, get_lead_pack
from apps.api.services.actions import ACTION_PRIORITY, get_instruction
from apps.api.services.leadpack import get_rating
from apps.api.schemas import (
    AuditFinding,
    AuditResponse,
    RedundancyFinding,
    RedundancyResponse,
    AutomationBatchResponse,
    AutomationDispatch,
    ClaimReleaseResponse,
    ClaimRequest,
    ClaimResponse,
    ClientReadyItem,
    ClientReadyResponse,
    DailyActionsResponse,
    DailyActionSummary,
    DailyClientReadyItem,
    DailyFollowupItem,
    DailyReviewItem,
    DailySourceWarning,
    EventItem,
    EventListResponse,
    HandoffBatchResponse,
    HandoffItem,
    LeadOperationalSummary,
    OperatorWorklistResponse,
    OpsSnapshotResponse,
    QueueResponse,
    ReviewClaimResponse,
    ReviewItem,
    ReviewQueueResponse,
    ProofVerifierFinding,
    ProofVerifierRequest,
    ProofVerifierResponse,
    FollowupAutomationItem,
    FollowupAutomationPayload,
    FollowupAutomationResponse,
    FollowupHandoffItem,
    FollowupHandoffResponse,
    FollowupItem,
    FollowupQueueResponse,
    OutcomeBySourceItem,
    OutcomeBySourceResponse,
    OutcomeRequest,
    OutcomeResponse,
    OutcomeSummaryResponse,
    DriftDetectorRequest,
    DriftDetectorResponse,
    DriftFinding,
    ScopeCriticFinding,
    ScopeCriticRequest,
    ScopeCriticResponse,
    SentinelFinding,
    SentinelResponse,
    SourceActionItem,
    SourceActionResponse,
    SourceIntelligenceItem,
    SourceIntelligenceOutcomes,
    SourceIntelligenceResponse,
    SourceIntelligenceTotals,
    SourceOutcomeActionItem,
    SourceOutcomeActionResponse,
    SourcePerformanceResponse,
    SourceStats,
    WorklistClaimedItem,
)

router = APIRouter()


def _priority_key(lead: LeadOperationalSummary) -> tuple[int, int, int]:
    """Sort key: alert DESC, action priority ASC, score DESC."""
    alert_rank = 0 if lead.alert else 1
    try:
        action_rank = ACTION_PRIORITY.index(lead.next_action)
    except ValueError:
        action_rank = len(ACTION_PRIORITY)
    return (alert_rank, action_rank, -lead.score)


@router.get("/internal/queue", response_model=QueueResponse)
def get_internal_queue(
    source: str | None = None,
    limit: int | None = Query(default=None, ge=1),
) -> QueueResponse:
    leads = _get_actionable_leads(source)
    sorted_leads = sorted(leads, key=_priority_key)
    urgent_count = sum(1 for lead in leads if lead.alert)
    total = len(sorted_leads)
    if limit is not None:
        sorted_leads = sorted_leads[:limit]
    return QueueResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        total=total,
        urgent_count=urgent_count,
        items=sorted_leads,
    )


@router.post("/internal/dispatch/claim", response_model=ClaimResponse)
def claim_dispatch_items(body: ClaimRequest) -> ClaimResponse:
    db = get_db()
    claimed: list[int] = []
    already_claimed: list[int] = []
    not_found: list[int] = []
    unique_ids = list(dict.fromkeys(body.lead_ids))
    for lead_id in unique_ids:
        row = db.execute("SELECT id FROM leads WHERE id = ?", (lead_id,)).fetchone()
        if row is None:
            not_found.append(lead_id)
            continue
        existing = db.execute(
            "SELECT id FROM dispatch_claims WHERE lead_id = ?", (lead_id,)
        ).fetchone()
        if existing is not None:
            already_claimed.append(lead_id)
            continue
        db.execute("INSERT INTO dispatch_claims (lead_id) VALUES (?)", (lead_id,))
        claimed.append(lead_id)
    db.commit()
    for cid in claimed:
        emit_event("lead.claimed", "lead", cid, "dispatch", {})
    return ClaimResponse(claimed=claimed, already_claimed=already_claimed, not_found=not_found)


@router.delete("/internal/dispatch/claim/{lead_id}", response_model=ClaimReleaseResponse)
def release_claim(lead_id: int) -> ClaimReleaseResponse:
    db = get_db()
    row = db.execute("SELECT id FROM leads WHERE id = ?", (lead_id,)).fetchone()
    if row is None:
        return ClaimReleaseResponse(lead_id=lead_id, status="not_found")
    existing = db.execute(
        "SELECT id FROM dispatch_claims WHERE lead_id = ?", (lead_id,)
    ).fetchone()
    if existing is None:
        return ClaimReleaseResponse(lead_id=lead_id, status="not_claimed")
    db.execute("DELETE FROM dispatch_claims WHERE lead_id = ?", (lead_id,))
    db.commit()
    emit_event("lead.released", "lead", lead_id, "dispatch", {})
    return ClaimReleaseResponse(lead_id=lead_id, status="released")


def _get_claimed_lead_ids() -> set[int]:
    db = get_db()
    rows = db.execute("SELECT lead_id FROM dispatch_claims").fetchall()
    return {row["lead_id"] for row in rows}


@router.get("/internal/dispatch", response_model=AutomationBatchResponse)
def get_dispatch_batch(
    source: str | None = None,
    limit: int | None = Query(default=None, ge=1),
    action: str | None = None,
) -> AutomationBatchResponse:
    leads = _get_actionable_leads(source)
    claimed_ids = _get_claimed_lead_ids()
    sorted_leads = sorted(
        [l for l in leads if l.lead_id not in claimed_ids], key=_priority_key
    )
    if action is not None:
        action = action.strip()
    if action:
        sorted_leads = [l for l in sorted_leads if l.next_action == action]
    total = len(sorted_leads)
    if limit is not None:
        sorted_leads = sorted_leads[:limit]
    now = datetime.now(timezone.utc).isoformat()
    items = []
    for i, lead in enumerate(sorted_leads):
        pack = get_lead_pack(lead.lead_id)
        try:
            priority = ACTION_PRIORITY.index(lead.next_action)
        except ValueError:
            priority = len(ACTION_PRIORITY)
        items.append(AutomationDispatch(
            lead_id=lead.lead_id,
            action=lead.next_action,
            instruction=lead.instruction,
            priority=priority,
            alert=lead.alert,
            payload=pack,
            generated_at=now,
        ))
    return AutomationBatchResponse(
        generated_at=now,
        total=total,
        items=items,
    )


_ACTION_CHANNEL: dict[str, str] = {
    "send_to_client": "email",
    "review_manually": "review",
    "request_more_info": "email",
    "enrich_first": "manual",
}


def _handoff_instruction(action: str, name: str, source: str, score: int) -> str:
    if action == "send_to_client":
        return f"Send lead pack to client — {name} ({source}, score {score})"
    if action == "review_manually":
        return f"Review lead before routing — {name} ({source}, score {score})"
    if action == "request_more_info":
        return f"Request more info from lead — {name} ({source}, score {score})"
    if action == "enrich_first":
        return f"Enrich lead data before action — {name} ({source}, score {score})"
    return f"Manual review required — {name} ({source}, score {score})"


@router.get("/internal/handoffs", response_model=HandoffBatchResponse)
def get_handoffs(
    source: str | None = None,
    limit: int | None = Query(default=None, ge=1),
    action: str | None = None,
) -> HandoffBatchResponse:
    leads = _get_actionable_leads(source)
    claimed_ids = _get_claimed_lead_ids()
    sorted_leads = sorted(
        [l for l in leads if l.lead_id not in claimed_ids], key=_priority_key
    )
    if action is not None:
        action = action.strip()
    if action:
        sorted_leads = [l for l in sorted_leads if l.next_action == action]
    total = len(sorted_leads)
    if limit is not None:
        sorted_leads = sorted_leads[:limit]
    now = datetime.now(timezone.utc).isoformat()
    items = []
    for lead in sorted_leads:
        pack = get_lead_pack(lead.lead_id)
        items.append(HandoffItem(
            lead_id=lead.lead_id,
            action=lead.next_action,
            channel=_ACTION_CHANNEL.get(lead.next_action, "manual"),
            instruction=_handoff_instruction(
                lead.next_action, lead.name, lead.source, lead.score
            ),
            payload=pack,
        ))
    return HandoffBatchResponse(
        generated_at=now,
        total=total,
        items=items,
    )


_CSV_DANGEROUS_PREFIXES = ("=", "+", "-", "@")

_HANDOFF_CSV_COLUMNS = ["lead_id", "action", "channel", "instruction", "name", "email", "source", "score", "rating"]


def _sanitize_csv_value(value: object) -> object:
    if isinstance(value, str) and value and value[0] in _CSV_DANGEROUS_PREFIXES:
        return "'" + value
    return value


@router.get("/internal/handoffs/export.csv", response_class=PlainTextResponse)
def export_handoffs_csv(
    source: str | None = None,
    limit: int | None = Query(default=None, ge=1),
    action: str | None = None,
) -> PlainTextResponse:
    leads = _get_actionable_leads(source)
    claimed_ids = _get_claimed_lead_ids()
    sorted_leads = sorted(
        [l for l in leads if l.lead_id not in claimed_ids], key=_priority_key
    )
    if action is not None:
        action = action.strip()
    if action:
        sorted_leads = [l for l in sorted_leads if l.next_action == action]
    if limit is not None:
        sorted_leads = sorted_leads[:limit]
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(_HANDOFF_CSV_COLUMNS)
    for lead in sorted_leads:
        pack = get_lead_pack(lead.lead_id)
        row = {
            "lead_id": lead.lead_id,
            "action": lead.next_action,
            "channel": _ACTION_CHANNEL.get(lead.next_action, "manual"),
            "instruction": _handoff_instruction(
                lead.next_action, lead.name, lead.source, lead.score
            ),
            "name": pack.name,
            "email": pack.email,
            "source": pack.source,
            "score": pack.score,
            "rating": pack.rating,
        }
        writer.writerow([_sanitize_csv_value(row[col]) for col in _HANDOFF_CSV_COLUMNS])
    return PlainTextResponse(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=handoffs.csv"},
    )


_REVIEWABLE_ACTIONS = {"send_to_client", "review_manually"}


@router.get("/internal/review", response_model=ReviewQueueResponse)
def get_review_queue(
    source: str | None = None,
    limit: int | None = Query(default=None, ge=1),
) -> ReviewQueueResponse:
    leads = _get_actionable_leads(source)
    claimed_ids = _get_claimed_lead_ids()
    reviewable = [
        l for l in leads
        if l.next_action in _REVIEWABLE_ACTIONS and l.lead_id not in claimed_ids
    ]
    reviewable.sort(key=lambda l: (0 if l.alert else 1, -l.score))
    urgent_count = sum(1 for l in reviewable if l.alert)
    if limit is not None:
        reviewable = reviewable[:limit]
    now = datetime.now(timezone.utc).isoformat()
    items = []
    for lead in reviewable:
        pack = get_lead_pack(lead.lead_id)
        items.append(ReviewItem(
            lead_id=lead.lead_id,
            name=pack.name,
            email=pack.email,
            source=pack.source,
            score=pack.score,
            rating=pack.rating,
            next_action=lead.next_action,
            instruction=lead.instruction,
            alert=lead.alert,
            created_at=pack.created_at,
        ))
    return ReviewQueueResponse(
        generated_at=now,
        total=len(items),
        urgent_count=urgent_count,
        items=items,
    )


@router.post("/internal/review/{lead_id}/claim", response_model=ReviewClaimResponse)
def claim_review_lead(lead_id: int) -> ReviewClaimResponse:
    db = get_db()
    row = db.execute("SELECT id FROM leads WHERE id = ?", (lead_id,)).fetchone()
    if row is None:
        return ReviewClaimResponse(lead_id=lead_id, status="not_found")
    pack = get_lead_pack(lead_id)
    if pack.next_action not in _REVIEWABLE_ACTIONS:
        return ReviewClaimResponse(lead_id=lead_id, status="not_reviewable")
    existing = db.execute(
        "SELECT id FROM dispatch_claims WHERE lead_id = ?", (lead_id,)
    ).fetchone()
    if existing is not None:
        return ReviewClaimResponse(lead_id=lead_id, status="already_claimed")
    db.execute("INSERT INTO dispatch_claims (lead_id) VALUES (?)", (lead_id,))
    db.commit()
    emit_event("lead.claimed", "lead", lead_id, "review", {})
    return ReviewClaimResponse(lead_id=lead_id, status="claimed")


@router.get("/internal/ops/snapshot", response_model=OpsSnapshotResponse)
def get_ops_snapshot() -> OpsSnapshotResponse:
    db = get_db()
    total_leads = db.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    all_actionable = _get_actionable_leads()
    claimed_ids = _get_claimed_lead_ids()
    unclaimed = [l for l in all_actionable if l.lead_id not in claimed_ids]
    pending_review = sum(
        1 for l in unclaimed if l.next_action in _REVIEWABLE_ACTIONS
    )
    urgent = sum(1 for l in unclaimed if l.alert)
    return OpsSnapshotResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        total_leads=total_leads,
        actionable=len(all_actionable),
        claimed=len(claimed_ids),
        pending_dispatch=len(unclaimed),
        pending_review=pending_review,
        urgent=urgent,
    )


@router.get("/internal/client-ready", response_model=ClientReadyResponse)
def get_client_ready() -> ClientReadyResponse:
    leads = _get_actionable_leads()
    claimed_ids = _get_claimed_lead_ids()
    ready = [
        l for l in leads
        if l.next_action == "send_to_client" and l.lead_id not in claimed_ids
    ]
    ready.sort(key=lambda l: -l.score)
    now = datetime.now(timezone.utc).isoformat()
    items = []
    for lead in ready:
        pack = get_lead_pack(lead.lead_id)
        items.append(ClientReadyItem(
            lead_id=lead.lead_id,
            name=pack.name,
            email=pack.email,
            source=pack.source,
            score=pack.score,
            rating=pack.rating,
            next_action=lead.next_action,
            instruction=lead.instruction,
            created_at=pack.created_at,
        ))
    return ClientReadyResponse(
        generated_at=now,
        total=len(items),
        items=items,
    )


@router.get("/internal/worklist", response_model=OperatorWorklistResponse)
def get_operator_worklist() -> OperatorWorklistResponse:
    leads = _get_actionable_leads()
    claimed_ids = _get_claimed_lead_ids()
    unclaimed = [l for l in leads if l.lead_id not in claimed_ids]

    # pending_review: reviewable unclaimed, alert DESC / score DESC
    reviewable = [l for l in unclaimed if l.next_action in _REVIEWABLE_ACTIONS]
    reviewable.sort(key=lambda l: (0 if l.alert else 1, -l.score))
    review_items = []
    for lead in reviewable:
        pack = get_lead_pack(lead.lead_id)
        review_items.append(ReviewItem(
            lead_id=lead.lead_id,
            name=pack.name,
            email=pack.email,
            source=pack.source,
            score=pack.score,
            rating=pack.rating,
            next_action=lead.next_action,
            instruction=lead.instruction,
            alert=lead.alert,
            created_at=pack.created_at,
        ))

    # client_ready: send_to_client unclaimed, score DESC
    ready = [l for l in unclaimed if l.next_action == "send_to_client"]
    ready.sort(key=lambda l: -l.score)
    ready_items = []
    for lead in ready:
        pack = get_lead_pack(lead.lead_id)
        ready_items.append(ClientReadyItem(
            lead_id=lead.lead_id,
            name=pack.name,
            email=pack.email,
            source=pack.source,
            score=pack.score,
            rating=pack.rating,
            next_action=lead.next_action,
            instruction=lead.instruction,
            created_at=pack.created_at,
        ))

    # recently_claimed: last 10 by claimed_at DESC
    db = get_db()
    claim_rows = db.execute(
        "SELECT dc.lead_id, dc.claimed_at, l.name, l.source, l.score "
        "FROM dispatch_claims dc JOIN leads l ON dc.lead_id = l.id "
        "ORDER BY dc.claimed_at DESC LIMIT 10"
    ).fetchall()
    claimed_items = [
        WorklistClaimedItem(
            lead_id=row["lead_id"],
            name=row["name"],
            source=row["source"],
            score=row["score"],
            claimed_at=row["claimed_at"],
        )
        for row in claim_rows
    ]

    return OperatorWorklistResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        pending_review=review_items,
        client_ready=ready_items,
        recently_claimed=claimed_items,
    )


@router.get("/internal/source-performance", response_model=SourcePerformanceResponse)
def get_source_performance() -> SourcePerformanceResponse:
    """Per-source performance breakdown.

    client_ready and review counts are derived from current actionable-lead
    semantics (score >= 40 OR has notes) and are intentionally independent
    of claim status — they measure source quality, not operational queue state.
    """
    db = get_db()
    rows = db.execute(
        "SELECT source, COUNT(*) AS total, ROUND(AVG(score), 1) AS avg_score "
        "FROM leads GROUP BY source ORDER BY total DESC"
    ).fetchall()
    # One pass over actionable leads for per-source action counts
    actionable = _get_actionable_leads()
    action_counts: dict[str, dict[str, int]] = {}
    for lead in actionable:
        counts = action_counts.setdefault(lead.source, {"client_ready": 0, "review": 0})
        if lead.next_action == "send_to_client":
            counts["client_ready"] += 1
        elif lead.next_action == "review_manually":
            counts["review"] += 1
    items = []
    for row in rows:
        src = row["source"]
        counts = action_counts.get(src, {"client_ready": 0, "review": 0})
        items.append(SourceStats(
            source=src,
            total=row["total"],
            avg_score=row["avg_score"],
            client_ready=counts["client_ready"],
            review=counts["review"],
        ))
    return SourcePerformanceResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        total_sources=len(items),
        items=items,
    )


def _source_recommendation(actionable: int, client_ready: int, review: int, avg_score: float) -> tuple[str, str]:
    """MVP heuristic recommendation for a source.

    Rules are derived from current source-performance signals. They are not
    stable business policy — they are initial heuristics that will need
    tuning as the scoring model and lead volume evolve.
    """
    if actionable < 3:
        return "review", "insufficient data"
    if client_ready / actionable >= 0.5:
        return "keep", "high client_ready rate"
    if avg_score >= 55:
        return "keep", "strong avg score"
    if review / actionable >= 0.3:
        return "review", "high review rate"
    return "review", "no strong signal"


@router.get("/internal/source-actions", response_model=SourceActionResponse)
def get_source_actions() -> SourceActionResponse:
    """Per-source operational recommendations.

    Recommendation rules are MVP heuristics derived from current
    source-performance signals, not stable business policy.
    """
    db = get_db()
    rows = db.execute(
        "SELECT source, COUNT(*) AS total, ROUND(AVG(score), 1) AS avg_score "
        "FROM leads GROUP BY source ORDER BY total DESC"
    ).fetchall()
    actionable_leads = _get_actionable_leads()
    per_source: dict[str, dict[str, int]] = {}
    for lead in actionable_leads:
        counts = per_source.setdefault(lead.source, {"actionable": 0, "client_ready": 0, "review": 0})
        counts["actionable"] += 1
        if lead.next_action == "send_to_client":
            counts["client_ready"] += 1
        elif lead.next_action == "review_manually":
            counts["review"] += 1
    items = []
    for row in rows:
        src = row["source"]
        counts = per_source.get(src, {"actionable": 0, "client_ready": 0, "review": 0})
        rec, rationale = _source_recommendation(
            counts["actionable"], counts["client_ready"], counts["review"], row["avg_score"]
        )
        items.append(SourceActionItem(
            source=src,
            total=row["total"],
            actionable=counts["actionable"],
            avg_score=row["avg_score"],
            client_ready=counts["client_ready"],
            review=counts["review"],
            recommendation=rec,
            rationale=rationale,
        ))
    return SourceActionResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        total_sources=len(items),
        items=items,
    )


@router.get("/internal/events", response_model=EventListResponse)
def get_events(
    event_type: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> EventListResponse:
    """Recent internal events. Read-only, no side effects."""
    db = get_db()
    conditions: list[str] = []
    params: list[str | int] = []
    if event_type is not None:
        conditions.append("event_type = ?")
        params.append(event_type.strip())
    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    query = f"SELECT * FROM events{where} ORDER BY id DESC LIMIT ?"
    params.append(limit)
    rows = db.execute(query, params).fetchall()
    items = []
    for row in rows:
        items.append(EventItem(
            id=row["id"],
            event_type=row["event_type"],
            entity_type=row["entity_type"],
            entity_id=row["entity_id"],
            origin_module=row["origin_module"],
            payload=json.loads(row["payload"]),
            created_at=row["created_at"],
        ))
    return EventListResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        total=len(items),
        items=items,
    )


# --- Sentinel checks ---

_STALE_CLAIM_HOURS = 24


def _check_stale_claims(db: "sqlite3.Connection") -> list[SentinelFinding]:
    """Claims older than _STALE_CLAIM_HOURS hours. Threshold is an MVP heuristic, not a stable policy or SLA."""
    rows = db.execute(
        "SELECT COUNT(*) AS cnt FROM dispatch_claims "
        "WHERE claimed_at <= datetime('now', ?)",
        (f"-{_STALE_CLAIM_HOURS} hours",),
    ).fetchone()
    count = rows["cnt"]
    if count == 0:
        return []
    severity = "medium" if count > 3 else "low"
    return [SentinelFinding(
        check="stale_claims",
        surface="dispatch",
        severity=severity,
        message=f"{count} claim(s) older than {_STALE_CLAIM_HOURS}h",
        recommended_action="Review claimed leads for stale claims",
    )]



def _check_source_needs_attention() -> list[SentinelFinding]:
    """Sources with recommendation=review and enough data to be meaningful."""
    db = get_db()
    rows = db.execute(
        "SELECT source, COUNT(*) AS total, ROUND(AVG(score), 1) AS avg_score "
        "FROM leads GROUP BY source ORDER BY total DESC"
    ).fetchall()
    actionable_leads = _get_actionable_leads()
    per_source: dict[str, dict[str, int]] = {}
    for lead in actionable_leads:
        counts = per_source.setdefault(lead.source, {"actionable": 0, "client_ready": 0, "review": 0})
        counts["actionable"] += 1
        if lead.next_action == "send_to_client":
            counts["client_ready"] += 1
        elif lead.next_action == "review_manually":
            counts["review"] += 1
    findings = []
    for row in rows:
        src = row["source"]
        counts = per_source.get(src, {"actionable": 0, "client_ready": 0, "review": 0})
        rec, rationale = _source_recommendation(
            counts["actionable"], counts["client_ready"], counts["review"], row["avg_score"]
        )
        if rec == "review" and rationale != "insufficient data":
            findings.append(SentinelFinding(
                check="source_needs_attention",
                surface="source-actions",
                severity="low",
                message=f"Source '{src}' flagged: {rationale}",
                recommended_action=f"Review source '{src}' performance and lead quality",
            ))
    return findings


def _check_event_spine_silent(db: "sqlite3.Connection") -> list[SentinelFinding]:
    """Detect event spine silence: no events at all, or recent leads with no recent events.

    Two rules:
    1. Total silence: leads exist but zero events ever recorded → high.
    2. Recent silence: leads created in the last 24h exist but zero events
       recorded in the last 24h → medium.  Indicates the spine may have
       stopped emitting while the system continues operating.
    """
    total_leads = db.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    if total_leads == 0:
        return []

    total_events = db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    if total_events == 0:
        return [SentinelFinding(
            check="event_spine_silent",
            surface="events",
            severity="high",
            message=f"{total_leads} leads exist but zero events recorded",
            recommended_action="Verify event emission is working",
        )]

    # Rule 2: recency check — recent leads but no recent events.
    recent_leads = db.execute(
        "SELECT COUNT(*) FROM leads WHERE created_at >= datetime('now', '-24 hours')"
    ).fetchone()[0]
    if recent_leads == 0:
        return []
    recent_events = db.execute(
        "SELECT COUNT(*) FROM events WHERE created_at >= datetime('now', '-24 hours')"
    ).fetchone()[0]
    if recent_events > 0:
        return []
    return [SentinelFinding(
        check="event_spine_silent",
        surface="events",
        severity="medium",
        message=(
            f"{recent_leads} leads created in last 24h but zero events "
            f"recorded in that window ({total_events} historical events exist)"
        ),
        recommended_action="Verify event emission is still active — historical events exist but recent activity is silent",
    )]


def _derive_status(findings: list[SentinelFinding]) -> str:
    severities = {f.severity for f in findings}
    if "high" in severities:
        return "alert"
    if "medium" in severities:
        return "watch"
    return "ok"


@router.get("/internal/sentinel", response_model=SentinelResponse)
def get_sentinel() -> SentinelResponse:
    """Quality sentinel — deterministic read-only operational health checks.
    No side effects, no persistence, no auto-remediation.
    """
    db = get_db()
    findings: list[SentinelFinding] = []
    findings.extend(_check_stale_claims(db))
    findings.extend(_check_source_needs_attention())
    findings.extend(_check_event_spine_silent(db))
    status = _derive_status(findings)
    return SentinelResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        status=status,
        total_findings=len(findings),
        findings=findings,
    )


# --- Audit checks ---


def _audit_source_surface_consistency() -> list[AuditFinding]:
    """source-performance and source-actions must agree on source list and per-source totals."""
    db = get_db()
    rows = db.execute(
        "SELECT source, COUNT(*) AS total FROM leads GROUP BY source ORDER BY total DESC"
    ).fetchall()
    if not rows:
        return []
    # Build per-source totals as both endpoints see them (same base query)
    perf_sources = {row["source"]: row["total"] for row in rows}

    # source-actions uses the same query — but also computes actionable counts.
    # The invariant: both surfaces enumerate the same sources with the same total.
    # We re-run the source-actions aggregation path to compare.
    actionable_leads = _get_actionable_leads()
    per_source: dict[str, dict[str, int]] = {}
    for lead in actionable_leads:
        per_source.setdefault(lead.source, {"actionable": 0, "client_ready": 0, "review": 0})
        per_source[lead.source]["actionable"] += 1

    # source-actions also queries the same leads GROUP BY — so it sees the same source set.
    # Check: every source in perf must appear in the actions query, and totals must match.
    action_rows = db.execute(
        "SELECT source, COUNT(*) AS total FROM leads GROUP BY source ORDER BY total DESC"
    ).fetchall()
    action_sources = {row["source"]: row["total"] for row in action_rows}

    mismatches: list[dict] = []
    all_sources = set(perf_sources.keys()) | set(action_sources.keys())
    for src in all_sources:
        perf_total = perf_sources.get(src)
        action_total = action_sources.get(src)
        if perf_total != action_total:
            mismatches.append({
                "source": src,
                "performance_total": perf_total,
                "actions_total": action_total,
            })

    if not mismatches:
        return []
    return [AuditFinding(
        check="source_surface_consistency",
        surface="source-performance / source-actions",
        severity="medium",
        message=f"{len(mismatches)} source(s) have mismatched totals between surfaces",
        detail={"mismatches": mismatches},
    )]


def _audit_ops_snapshot_arithmetic() -> list[AuditFinding]:
    """Ops snapshot must satisfy: pending_dispatch == actionable - claimed."""
    all_actionable = _get_actionable_leads()
    claimed_ids = _get_claimed_lead_ids()
    unclaimed = [l for l in all_actionable if l.lead_id not in claimed_ids]

    actionable = len(all_actionable)
    claimed = len(claimed_ids)
    pending_dispatch = len(unclaimed)
    expected = actionable - claimed

    if pending_dispatch == expected:
        return []
    return [AuditFinding(
        check="ops_snapshot_arithmetic",
        surface="ops/snapshot",
        severity="high",
        message=f"pending_dispatch ({pending_dispatch}) != actionable ({actionable}) - claimed ({claimed}) = {expected}",
        detail={
            "actionable": actionable,
            "claimed": claimed,
            "pending_dispatch": pending_dispatch,
            "expected_pending": expected,
        },
    )]


def _derive_audit_status(findings: list[AuditFinding]) -> str:
    severities = {f.severity for f in findings}
    if "high" in severities:
        return "fail"
    if "medium" in severities:
        return "warn"
    return "pass"


@router.get("/internal/audit", response_model=AuditResponse)
def get_audit() -> AuditResponse:
    """Module audit — deterministic cross-module consistency checks.
    Read-only, no side effects, no persistence.
    """
    findings: list[AuditFinding] = []
    findings.extend(_audit_source_surface_consistency())
    findings.extend(_audit_ops_snapshot_arithmetic())
    status = _derive_audit_status(findings)
    return AuditResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        status=status,
        total_findings=len(findings),
        findings=findings,
    )


# --- Redundancy checks ---

# Project root: resolved once at import time.
_PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Explicit candidate list of skills whose purpose is fully absorbed by
# current .claude/CLAUDE.md governance.  Each entry maps the skill
# directory/file stem to the CLAUDE.md sections that absorb it.
_SKILLS_REDUNDANT_CANDIDATES: dict[str, tuple[str, str, str]] = {
    "architecture_guardian": (
        "CLAUDE.md §2 (non-negotiable rules), §4 (planning), §6 (reopen), §10 (approval boundaries)",
        "low",
        "All 7 rules are literal subsets of current global CLAUDE.md sections",
    ),
    "human_approval_guard": (
        "CLAUDE.md §10 (approval boundaries), §11 (high-impact rule / triad)",
        "low",
        "Approval categories are a strict subset of §10; triad covered by §11",
    ),
    "scope-guard": (
        "CLAUDE.md §2 (scope rules), §4 (planning/execution), §6 (reopen rules)",
        "low",
        "Scope protection rules fully restated in global governance",
    ),
    "clean_code_enforcer": (
        "CLAUDE.md §8 (engineering rules), §2 (no refactor outside scope); apps/api/CLAUDE.md DEFAULTS",
        "low",
        "Engineering and scope rules in global + module CLAUDE.md cover all 7 enforcer rules",
    ),
}


def _find_skill_files() -> list[tuple[str, str]]:
    """Return (stem, relative_path) for each skill file under skills/."""
    skills_dir = _PROJECT_ROOT / "skills"
    if not skills_dir.is_dir():
        return []
    results: list[tuple[str, str]] = []
    for path in sorted(skills_dir.rglob("*")):
        if path.is_file() and path.suffix in (".md",):
            # stem: directory name for SKILL.md, filename stem for flat files
            if path.name == "SKILL.md":
                stem = path.parent.name
            else:
                stem = path.stem
            rel = str(path.relative_to(_PROJECT_ROOT)).replace("\\", "/")
            results.append((stem, rel))
    return results


def _check_skills_redundant() -> list[RedundancyFinding]:
    """Report skills from the explicit candidate list that still exist on disk."""
    skill_files = _find_skill_files()
    if not skill_files:
        return []
    findings: list[RedundancyFinding] = []
    for stem, rel_path in skill_files:
        if stem in _SKILLS_REDUNDANT_CANDIDATES:
            absorbed_by, removal_risk, why_now = _SKILLS_REDUNDANT_CANDIDATES[stem]
            findings.append(RedundancyFinding(
                type="overlap",
                targets=[rel_path],
                severity="low",
                message=f"Skill '{stem}' appears fully absorbed by current governance: {absorbed_by}",
                recommended_action="archive_candidate",
                confidence="medium",
                removal_risk=removal_risk,
                why_now=why_now,
            ))
    return findings


def _normalize_rule_line(line: str) -> str:
    """Strip whitespace, bullet markers, numbering, and lowercase for comparison."""
    s = line.strip()
    # Remove leading bullet markers: -, *, >, numbered (1. 2.)
    s = re.sub(r"^[-*>]\s*", "", s)
    s = re.sub(r"^\d+\.\s*", "", s)
    s = s.strip().lower()
    return s


def _extract_rule_lines(text: str, min_length: int = 25) -> set[str]:
    """Extract normalized non-trivial lines from a CLAUDE.md file."""
    lines: set[str] = set()
    for raw in text.splitlines():
        normalized = _normalize_rule_line(raw)
        if len(normalized) >= min_length:
            lines.add(normalized)
    return lines


def _check_claude_md_duplication() -> list[RedundancyFinding]:
    """Find module-local CLAUDE.md files with literal rule duplication from the global file."""
    global_path = _PROJECT_ROOT / ".claude" / "CLAUDE.md"
    if not global_path.is_file():
        return []
    try:
        global_text = global_path.read_text(encoding="utf-8")
    except OSError:
        return []
    global_rules = _extract_rule_lines(global_text)
    if not global_rules:
        return []

    # Known module-local CLAUDE.md locations
    local_candidates = [
        _PROJECT_ROOT / "apps" / "api" / "CLAUDE.md",
        _PROJECT_ROOT / "apps" / "api" / "routes" / "CLAUDE.md",
        _PROJECT_ROOT / "docs" / "CLAUDE.md",
        _PROJECT_ROOT / "core" / "CLAUDE.md",
        _PROJECT_ROOT / "apps" / "api" / "automations" / "CLAUDE.md",
    ]

    findings: list[RedundancyFinding] = []
    for local_path in local_candidates:
        if not local_path.is_file():
            continue
        try:
            local_text = local_path.read_text(encoding="utf-8")
        except OSError:
            continue
        local_rules = _extract_rule_lines(local_text)
        duplicates = global_rules & local_rules
        if len(duplicates) >= 2:
            rel = str(local_path.relative_to(_PROJECT_ROOT)).replace("\\", "/")
            findings.append(RedundancyFinding(
                type="overlap",
                targets=[rel, ".claude/CLAUDE.md"],
                severity="low",
                message=f"{len(duplicates)} rule line(s) in '{rel}' are literal duplicates of global CLAUDE.md",
                recommended_action="merge",
                confidence="high",
                removal_risk="low",
                why_now="Literal duplication adds maintenance cost without adding value",
            ))
    return findings


_STUB_MARKER = "Not yet implemented. No code exists here."


def _check_dormant_stubs() -> list[RedundancyFinding]:
    """Report CLAUDE.md files that explicitly declare themselves as stubs."""
    stub_candidates = [
        _PROJECT_ROOT / "core" / "CLAUDE.md",
        _PROJECT_ROOT / "apps" / "api" / "automations" / "CLAUDE.md",
    ]
    findings: list[RedundancyFinding] = []
    for path in stub_candidates:
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if _STUB_MARKER in text:
            rel = str(path.relative_to(_PROJECT_ROOT)).replace("\\", "/")
            findings.append(RedundancyFinding(
                type="dormant",
                targets=[rel],
                severity="low",
                message=f"'{rel}' is an explicit stub with no implementation behind it",
                recommended_action="keep",
                confidence="high",
                removal_risk="low",
                why_now="Stub exists as placeholder; no code depends on it",
            ))
    return findings


def _derive_redundancy_status(findings: list[RedundancyFinding]) -> str:
    severities = {f.severity for f in findings}
    if "high" in severities:
        return "alert"
    if "medium" in severities:
        return "watch"
    return "ok"


@router.get("/internal/redundancy", response_model=RedundancyResponse)
def get_redundancy() -> RedundancyResponse:
    """Redundancy / waste bot — deterministic read-only report of
    redundant, overlapping, or absorbed project weight.
    Inspects filesystem only. No side effects, no persistence, no modifications.
    """
    findings: list[RedundancyFinding] = []
    findings.extend(_check_skills_redundant())
    findings.extend(_check_claude_md_duplication())
    findings.extend(_check_dormant_stubs())
    status = _derive_redundancy_status(findings)
    return RedundancyResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        areas_scanned=["skills/", "CLAUDE.md hierarchy"],
        overall_status=status,
        total_findings=len(findings),
        findings=findings,
    )


# --- Scope critic checks ---

import fnmatch

_PROTECTED_PATTERNS = [
    ".claude/*",
    "skills/*",
    "README.md",
    "Dockerfile",
    "docker-compose*",
    ".gitignore",
]

# Ordered longest-prefix-first so matching is deterministic.
_AREA_PREFIXES: list[tuple[str, str]] = [
    ("apps/api/routes/", "apps/api/routes"),
    ("apps/api/services/", "apps/api/services"),
    ("apps/api/automations/", "apps/api/automations"),
    ("apps/api/", "apps/api"),
    (".claude/", ".claude"),
    ("skills/", "skills"),
    ("docs/", "docs"),
    ("tests/", "tests"),
    ("core/", "core"),
    ("deploy/", "deploy"),
]


def _file_area(filepath: str) -> str:
    """Map a file path to its repo area using longest-prefix match."""
    normalized = filepath.replace("\\", "/")
    for prefix, area in _AREA_PREFIXES:
        if normalized.startswith(prefix):
            return area
    return "root"


def _matches_protected(filepath: str) -> bool:
    """Check if filepath matches any protected pattern."""
    normalized = filepath.replace("\\", "/")
    for pattern in _PROTECTED_PATTERNS:
        if fnmatch.fnmatch(normalized, pattern):
            return True
        # Also match exact name for root-level files
        basename = normalized.rsplit("/", 1)[-1] if "/" in normalized else normalized
        if fnmatch.fnmatch(basename, pattern):
            return True
    return False


def _protected_area(filepath: str) -> str:
    """Return the protected area string for a protected file."""
    normalized = filepath.replace("\\", "/")
    if normalized.startswith(".claude/") or normalized == ".claude":
        return ".claude"
    if normalized.startswith("skills/") or normalized == "skills":
        return "skills"
    return normalized.rsplit("/", 1)[-1] if "/" in normalized else normalized


def _area_in_items(area: str, items: list[str]) -> bool:
    """Check if a protected area is explicitly mentioned in a list of scope items."""
    area_lower = area.lower()
    for item in items:
        item_lower = item.lower().strip()
        if area_lower in item_lower:
            return True
    return False


def _check_sensitive_file_intrusion(req: ScopeCriticRequest) -> list[ScopeCriticFinding]:
    """Protected files in expected_files must be explicitly covered in scope and not contradicted by out_of_scope."""
    violations: list[str] = []
    for filepath in req.expected_files:
        if not _matches_protected(filepath):
            continue
        area = _protected_area(filepath)
        in_scope = _area_in_items(area, req.scope)
        in_out_of_scope = _area_in_items(area, req.out_of_scope)
        if not in_scope:
            violations.append(f"{filepath} (area '{area}' not in scope)")
        elif in_out_of_scope:
            violations.append(f"{filepath} (area '{area}' contradicted by out_of_scope)")
    if not violations:
        return []
    return [ScopeCriticFinding(
        check="sensitive_file_intrusion",
        severity="high",
        message=f"{len(violations)} protected file(s) in expected_files without proper scope coverage",
        evidence=violations,
    )]


def _check_file_spread_risk(req: ScopeCriticRequest) -> list[ScopeCriticFinding]:
    """Flag proposals touching >4 distinct repo areas."""
    areas = {_file_area(f) for f in req.expected_files}
    if len(areas) <= 4:
        return []
    return [ScopeCriticFinding(
        check="file_spread_risk",
        severity="medium",
        message=f"Expected files span {len(areas)} distinct areas (threshold: 4)",
        evidence=sorted(areas),
    )]


_DISMISSIVE_VALUES = frozenset([
    "nothing", "none", "n/a", "na", "tbd", "-",
])

_RISK_DISMISSIVE_VALUES = _DISMISSIVE_VALUES | frozenset([
    "no risk", "low risk", "low", "none expected",
])

_MINIMUM_PLACEHOLDERS = frozenset([
    "tbd", "get it working", "make it work", "whatever works",
    "just do it", "same as goal", "see above", "see goal",
])


def _check_weak_out_of_scope(req: ScopeCriticRequest) -> list[ScopeCriticFinding]:
    """Flag if ALL out_of_scope entries are trivially dismissive."""
    dismissive = [
        item for item in req.out_of_scope
        if item.strip().lower() in _DISMISSIVE_VALUES
    ]
    if len(dismissive) < len(req.out_of_scope):
        return []
    return [ScopeCriticFinding(
        check="weak_out_of_scope",
        severity="medium",
        message="All out_of_scope entries are trivially dismissive",
        evidence=dismissive,
    )]


def _check_minimum_scope_mismatch(req: ScopeCriticRequest) -> list[ScopeCriticFinding]:
    """Flag generic minimum_acceptable that contradicts non-trivial scope/files."""
    normalized_min = req.minimum_acceptable.strip().lower()
    if normalized_min not in _MINIMUM_PLACEHOLDERS:
        return []
    non_trivial = len(req.scope) > 2 or len(req.expected_files) > 3
    if not non_trivial:
        return []
    return [ScopeCriticFinding(
        check="minimum_scope_mismatch",
        severity="medium",
        message="Generic minimum_acceptable with non-trivial scope",
        evidence=[
            f"minimum_acceptable: '{req.minimum_acceptable}'",
            f"scope items: {len(req.scope)}",
            f"expected_files: {len(req.expected_files)}",
        ],
    )]


def _check_risk_unacknowledged(req: ScopeCriticRequest) -> list[ScopeCriticFinding]:
    """Flag trivially dismissive main_risk."""
    if req.main_risk.strip().lower() not in _RISK_DISMISSIVE_VALUES:
        return []
    return [ScopeCriticFinding(
        check="risk_unacknowledged",
        severity="low",
        message="main_risk appears trivially dismissive",
        evidence=[req.main_risk],
    )]


def _derive_scope_critic_status(findings: list[ScopeCriticFinding]) -> str:
    severities = {f.severity for f in findings}
    if "high" in severities:
        return "block"
    if "medium" in severities:
        return "watch"
    return "ok"


@router.post("/internal/scope-critic", response_model=ScopeCriticResponse)
def post_scope_critic(body: ScopeCriticRequest) -> ScopeCriticResponse:
    """Scope critic — deterministic structural review of a BUILD/HARDEN proposal.
    Read-only, no persistence, no side effects.
    """
    findings: list[ScopeCriticFinding] = []
    findings.extend(_check_sensitive_file_intrusion(body))
    findings.extend(_check_file_spread_risk(body))
    findings.extend(_check_weak_out_of_scope(body))
    findings.extend(_check_minimum_scope_mismatch(body))
    findings.extend(_check_risk_unacknowledged(body))
    status = _derive_scope_critic_status(findings)
    return ScopeCriticResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        status=status,
        total_findings=len(findings),
        findings=findings,
    )


# --- Proof verifier checks ---

_CLOSURE_LANGUAGE = frozenset([
    "done", "complete", "production-ready", "fully verified",
    "fully supported", "no debt",
])

_OVERCLAIM_LANGUAGE = frozenset([
    "complete", "production-ready", "fully supported", "no debt", "done",
])

_TEST_EVIDENCE_KEYWORDS = frozenset([
    "test", "pytest", "check", "verif", "spec", "assert",
])

# Pre-compiled prefix-word-boundary patterns for test evidence detection.
# Uses \b only at the start so "tested" matches "test" but "inspected" does not match "spec".
_TEST_EVIDENCE_PATTERNS = [
    re.compile(r"\b" + kw, re.IGNORECASE)
    for kw in _TEST_EVIDENCE_KEYWORDS
]


def _file_has_specific_evidence(filepath: str, evidence_items: list[str]) -> bool:
    """Check if a file is specifically mentioned in evidence items.

    Prefers more specific path substrings before falling back to basename.
    """
    normalized = filepath.replace("\\", "/")
    # Try progressively less specific matches:
    # 1. Full path match
    # 2. Path with parent directory (e.g. "routes/internal.py")
    # 3. Basename only (e.g. "internal.py")
    candidates: list[str] = [normalized]
    parts = normalized.rsplit("/", 1)
    if "/" in normalized:
        # Add parent/basename
        parent_parts = normalized.rsplit("/", 2)
        if len(parent_parts) >= 2:
            candidates.append("/".join(parent_parts[-2:]))
        candidates.append(parts[-1])
    else:
        candidates.append(normalized)

    for item in evidence_items:
        item_lower = item.lower()
        for candidate in candidates:
            if candidate.lower() in item_lower:
                return True
    return False


def _check_unverified_gap(req: ProofVerifierRequest) -> list[ProofVerifierFinding]:
    """Claimed_not_verified is non-empty but status_claim uses closure language."""
    if not req.claimed_not_verified:
        return []
    status_lower = req.status_claim.strip().lower()
    if status_lower not in _CLOSURE_LANGUAGE:
        return []
    return [ProofVerifierFinding(
        check="unverified_gap",
        severity="high",
        message=f"Status claims '{req.status_claim}' but {len(req.claimed_not_verified)} item(s) marked not verified",
        evidence=[
            f"status_claim: '{req.status_claim}'",
            *[f"not_verified: '{item}'" for item in req.claimed_not_verified],
        ],
        blocks_closure=True,
        confidence="high",
    )]


def _check_untested_changes(req: ProofVerifierRequest) -> list[ProofVerifierFinding]:
    """Files in files_touched with no specific mention in tests_run or claimed_verified."""
    all_evidence = req.tests_run + req.claimed_verified
    unmatched = [
        f for f in req.files_touched
        if not _file_has_specific_evidence(f, all_evidence)
    ]
    if not unmatched:
        return []
    return [ProofVerifierFinding(
        check="untested_changes",
        severity="medium",
        message=f"{len(unmatched)} file(s) touched with no specific verification evidence — include file path or name in claimed_verified or tests_run to resolve",
        evidence=unmatched,
        blocks_closure=False,
        confidence="medium",
    )]


def _check_empty_test_evidence(req: ProofVerifierRequest) -> list[ProofVerifierFinding]:
    """No test evidence at all: tests_run is empty AND claimed_verified has no test-like references."""
    if req.tests_run:
        return []
    has_test_ref = any(
        any(pat.search(item) for pat in _TEST_EVIDENCE_PATTERNS)
        for item in req.claimed_verified
    )
    if has_test_ref:
        return []
    return [ProofVerifierFinding(
        check="empty_test_evidence",
        severity="high",
        message="No test evidence provided: tests_run is empty and claimed_verified contains no test references",
        evidence=[
            "tests_run: []",
            f"claimed_verified entries: {len(req.claimed_verified)}",
        ],
        blocks_closure=True,
        confidence="high",
    )]


def _check_overclaim_status(req: ProofVerifierRequest) -> list[ProofVerifierFinding]:
    """Status claim uses overconfident language warned against in CLAUDE.md anti-complacency."""
    status_lower = req.status_claim.strip().lower()
    if status_lower not in _OVERCLAIM_LANGUAGE:
        return []
    return [ProofVerifierFinding(
        check="overclaim_status",
        severity="low",
        message=f"Status '{req.status_claim}' uses language flagged by anti-complacency rules",
        evidence=[f"status_claim: '{req.status_claim}'"],
        blocks_closure=False,
        confidence="high",
    )]


def _check_verification_claim_mismatch(req: ProofVerifierRequest) -> list[ProofVerifierFinding]:
    """Claiming zero gaps but fewer than half of touched files have specific verification evidence."""
    if req.claimed_not_verified:
        return []  # gaps are acknowledged, no mismatch
    all_evidence = req.tests_run + req.claimed_verified
    verified_count = sum(
        1 for f in req.files_touched
        if _file_has_specific_evidence(f, all_evidence)
    )
    total = len(req.files_touched)
    if total == 0:
        return []
    ratio = verified_count / total
    if ratio >= 0.5:
        return []
    unmatched = [
        f for f in req.files_touched
        if not _file_has_specific_evidence(f, all_evidence)
    ]
    return [ProofVerifierFinding(
        check="verification_claim_mismatch",
        severity="medium",
        message=f"Claims zero unverified items but only {verified_count}/{total} files have specific evidence",
        evidence=[
            f"coverage ratio: {ratio:.2f}",
            *[f"unmatched: '{f}'" for f in unmatched],
        ],
        blocks_closure=False,
        confidence="medium",
    )]


def _derive_proof_verifier_status(findings: list[ProofVerifierFinding]) -> str:
    if any(f.blocks_closure for f in findings):
        return "not_close"
    severities = {f.severity for f in findings}
    if "high" in severities or "medium" in severities:
        return "watch"
    return "close"


@router.post("/internal/proof-verifier", response_model=ProofVerifierResponse)
def post_proof_verifier(body: ProofVerifierRequest) -> ProofVerifierResponse:
    """Proof verifier — deterministic post-build review of a completion report.
    Read-only, no persistence, no side effects, no file modifications.
    """
    findings: list[ProofVerifierFinding] = []
    findings.extend(_check_unverified_gap(body))
    findings.extend(_check_untested_changes(body))
    findings.extend(_check_empty_test_evidence(body))
    findings.extend(_check_overclaim_status(body))
    findings.extend(_check_verification_claim_mismatch(body))
    status = _derive_proof_verifier_status(findings)
    return ProofVerifierResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        status=status,
        total_findings=len(findings),
        findings=findings,
    )


# --- Drift Detector ---


def _normalize_path(s: str) -> str:
    """Normalize a file path for comparison: lowercase, strip, forward slashes, no trailing slash."""
    return s.strip().lower().replace("\\", "/").rstrip("/")


def _normalize_text(s: str) -> str:
    """Normalize text for comparison: lowercase, strip, collapse whitespace."""
    return re.sub(r"\s+", " ", s.strip().lower())


def _check_file_addition_drift(req: DriftDetectorRequest) -> list[DriftFinding]:
    """Files in report_files_touched not in plan_expected_files."""
    planned = {_normalize_path(f) for f in req.plan_expected_files}
    touched = {_normalize_path(f) for f in req.report_files_touched}
    added = sorted(touched - planned)
    if not added:
        return []
    return [DriftFinding(
        check="file_addition_drift",
        severity="high",
        message=f"{len(added)} file(s) touched but not in plan: {', '.join(added)}",
        plan_value=sorted(planned),
        report_value=added,
        requires_justification=True,
    )]


def _check_file_omission_drift(req: DriftDetectorRequest) -> list[DriftFinding]:
    """Files in plan_expected_files not in report_files_touched."""
    planned = {_normalize_path(f) for f in req.plan_expected_files}
    touched = {_normalize_path(f) for f in req.report_files_touched}
    omitted = sorted(planned - touched)
    if not omitted:
        return []
    return [DriftFinding(
        check="file_omission_drift",
        severity="medium",
        message=f"{len(omitted)} planned file(s) not touched: {', '.join(omitted)}",
        plan_value=omitted,
        report_value=sorted(touched),
        requires_justification=True,
    )]


def _check_classification_drift(req: DriftDetectorRequest) -> list[DriftFinding]:
    """Plan classification differs from report classification."""
    plan_cls = req.plan_classification.strip().lower()
    report_cls = req.report_classification.strip().lower()
    if plan_cls == report_cls:
        return []
    return [DriftFinding(
        check="classification_drift",
        severity="medium",
        message=f"Classification changed: plan='{req.plan_classification.strip()}' → report='{req.report_classification.strip()}'",
        plan_value=[req.plan_classification.strip()],
        report_value=[req.report_classification.strip()],
        requires_justification=True,
    )]


def _check_out_of_scope_intrusion(req: DriftDetectorRequest) -> list[DriftFinding]:
    """Items in report_claimed_changes that exactly match items in plan_out_of_scope (after normalization)."""
    out_of_scope = {_normalize_text(item) for item in req.plan_out_of_scope}
    claimed = {_normalize_text(item) for item in req.report_claimed_changes}
    intrusions = sorted(out_of_scope & claimed)
    if not intrusions:
        return []
    return [DriftFinding(
        check="out_of_scope_intrusion",
        severity="high",
        message=f"{len(intrusions)} claimed change(s) match out-of-scope items: {', '.join(intrusions)}",
        plan_value=sorted(out_of_scope),
        report_value=intrusions,
        requires_justification=True,
    )]


def _derive_drift_detector_status(findings: list[DriftFinding]) -> str:
    severities = {f.severity for f in findings}
    if "high" in severities:
        return "drift"
    if "medium" in severities:
        return "watch"
    return "clean"


@router.post("/internal/drift-detector", response_model=DriftDetectorResponse)
def post_drift_detector(body: DriftDetectorRequest) -> DriftDetectorResponse:
    """Drift detector — deterministic plan-vs-execution cross-reference.
    Advisory only. Read-only, no persistence, no side effects.
    """
    findings: list[DriftFinding] = []
    findings.extend(_check_file_addition_drift(body))
    findings.extend(_check_file_omission_drift(body))
    findings.extend(_check_classification_drift(body))
    findings.extend(_check_out_of_scope_intrusion(body))
    status = _derive_drift_detector_status(findings)
    return DriftDetectorResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        status=status,
        total_findings=len(findings),
        findings=findings,
    )


# --- Outcome feedback ---

_OUTCOME_VALUES = ["contacted", "qualified", "won", "lost", "no_answer", "bad_fit"]


@router.post("/internal/outcomes", response_model=OutcomeResponse, status_code=201)
def post_outcome(body: OutcomeRequest) -> OutcomeResponse:
    """Record or update the real-world outcome for a lead. Upsert semantics."""
    db = get_db()
    lead = db.execute("SELECT id FROM leads WHERE id = ?", (body.lead_id,)).fetchone()
    if lead is None:
        raise HTTPException(status_code=404, detail=f"Lead {body.lead_id} not found")
    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        """
        INSERT INTO lead_outcomes (lead_id, outcome, reason, notes, recorded_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(lead_id) DO UPDATE SET
            outcome = excluded.outcome,
            reason = excluded.reason,
            notes = excluded.notes,
            recorded_at = excluded.recorded_at
        """,
        (body.lead_id, body.outcome, body.reason, body.notes, now),
    )
    db.commit()
    emit_event(
        "lead.outcome_recorded", "lead", body.lead_id, "outcomes",
        {"outcome": body.outcome},
    )
    return OutcomeResponse(
        lead_id=body.lead_id,
        outcome=body.outcome,
        reason=body.reason,
        notes=body.notes,
        recorded_at=now,
    )


@router.get("/internal/outcomes/summary", response_model=OutcomeSummaryResponse)
def get_outcome_summary() -> OutcomeSummaryResponse:
    """Aggregated outcome counts across all leads."""
    db = get_db()
    rows = db.execute(
        "SELECT outcome, COUNT(*) as cnt FROM lead_outcomes GROUP BY outcome"
    ).fetchall()
    counts = {row["outcome"]: row["cnt"] for row in rows}
    by_outcome = {v: counts.get(v, 0) for v in _OUTCOME_VALUES}
    total = sum(by_outcome.values())
    return OutcomeSummaryResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        total=total,
        by_outcome=by_outcome,
    )


@router.get("/internal/outcomes/by-source", response_model=OutcomeBySourceResponse)
def get_outcomes_by_source() -> OutcomeBySourceResponse:
    """Outcome counts broken down by lead source."""
    db = get_db()
    rows = db.execute(
        """
        SELECT l.source, lo.outcome, COUNT(*) as cnt
        FROM lead_outcomes lo
        JOIN leads l ON l.id = lo.lead_id
        GROUP BY l.source, lo.outcome
        """
    ).fetchall()
    # Pivot: group by source, fill zero counts
    source_map: dict[str, dict[str, int]] = {}
    for row in rows:
        src = row["source"]
        if src not in source_map:
            source_map[src] = {v: 0 for v in _OUTCOME_VALUES}
        source_map[src][row["outcome"]] = row["cnt"]
    items = [
        OutcomeBySourceItem(
            source=src,
            total=sum(counts.values()),
            **counts,
        )
        for src, counts in sorted(source_map.items())
    ]
    return OutcomeBySourceResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        total_sources=len(items),
        items=items,
    )


@router.get("/internal/followup-queue", response_model=FollowupQueueResponse)
def get_followup_queue() -> FollowupQueueResponse:
    """Leads whose latest outcome is no_answer, ordered by score DESC for retry."""
    db = get_db()
    rows = db.execute(
        """
        SELECT lo.lead_id, lo.reason, lo.notes, lo.recorded_at
        FROM lead_outcomes lo
        WHERE lo.outcome = 'no_answer'
        """
    ).fetchall()
    claimed_ids = _get_claimed_lead_ids()
    items: list[FollowupItem] = []
    for row in rows:
        if row["lead_id"] in claimed_ids:
            continue
        pack = get_lead_pack(row["lead_id"])
        items.append(FollowupItem(
            lead_id=pack.lead_id,
            name=pack.name,
            email=pack.email,
            source=pack.source,
            score=pack.score,
            rating=pack.rating,
            next_action=pack.next_action,
            instruction=get_instruction(pack.next_action),
            outcome="no_answer",
            outcome_reason=row["reason"],
            outcome_notes=row["notes"],
            outcome_recorded_at=row["recorded_at"],
        ))
    items.sort(key=lambda x: (-x.score, x.lead_id))
    return FollowupQueueResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        total=len(items),
        items=items,
    )


# --- Source Outcome Actions ---

_OUTCOME_MIN_DATA = 3


def _source_outcome_recommendation(
    counts: dict[str, int], total: int
) -> tuple[str, str, bool]:
    """Return (recommendation, rationale, data_sufficient) for a source."""
    if total < _OUTCOME_MIN_DATA:
        return (
            "review",
            f"insufficient outcome data (n={total})",
            False,
        )
    positive = counts["won"] + counts["qualified"]
    negative = counts["bad_fit"] + counts["lost"]
    no_answer = counts["no_answer"]
    pos_pct = round(positive / total * 100)
    neg_pct = round(negative / total * 100)
    na_pct = round(no_answer / total * 100)
    if positive / total >= 0.5:
        return "keep", f"strong qualified/won signal ({pos_pct}%)", True
    if negative / total >= 0.5:
        return "deprioritize", f"high bad_fit/lost rate ({neg_pct}%)", True
    if no_answer / total >= 0.5:
        return (
            "review",
            f"high no_answer rate ({na_pct}%) — investigate responsiveness",
            True,
        )
    return "review", "mixed outcome pattern — manual review recommended", True


@router.get(
    "/internal/source-outcome-actions",
    response_model=SourceOutcomeActionResponse,
)
def get_source_outcome_actions() -> SourceOutcomeActionResponse:
    """Source recommendations based on recorded outcome data."""
    db = get_db()
    rows = db.execute(
        """
        SELECT l.source, lo.outcome, COUNT(*) as cnt
        FROM lead_outcomes lo
        JOIN leads l ON l.id = lo.lead_id
        GROUP BY l.source, lo.outcome
        """
    ).fetchall()
    source_map: dict[str, dict[str, int]] = {}
    for row in rows:
        src = row["source"]
        if src not in source_map:
            source_map[src] = {v: 0 for v in _OUTCOME_VALUES}
        source_map[src][row["outcome"]] = row["cnt"]
    items: list[SourceOutcomeActionItem] = []
    for src, counts in sorted(source_map.items()):
        total = sum(counts.values())
        recommendation, rationale, data_sufficient = (
            _source_outcome_recommendation(counts, total)
        )
        items.append(
            SourceOutcomeActionItem(
                source=src,
                total_outcomes=total,
                **counts,
                recommendation=recommendation,
                rationale=rationale,
                data_sufficient=data_sufficient,
            )
        )
    return SourceOutcomeActionResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        total_sources=len(items),
        items=items,
    )


# --- Daily Actions ---

_DAILY_CAP = 5


@router.get("/internal/daily-actions", response_model=DailyActionsResponse)
def get_daily_actions() -> DailyActionsResponse:
    """Compact daily action surface composing existing operational signals."""
    db = get_db()

    # 1. Actionable leads, excluding claimed
    actionable = _get_actionable_leads(source=None)
    claimed_ids = _get_claimed_lead_ids()
    unclaimed = [l for l in actionable if l.lead_id not in claimed_ids]

    # 2. Review items (review_manually, priority-sorted)
    all_review = sorted(
        [l for l in unclaimed if l.next_action == "review_manually"],
        key=_priority_key,
    )
    top_review = [
        DailyReviewItem(
            lead_id=l.lead_id,
            name=l.name,
            source=l.source,
            score=l.score,
            rating=l.rating,
            next_action=l.next_action,
            alert=l.alert,
        )
        for l in all_review[:_DAILY_CAP]
    ]

    # 3. Client-ready items (send_to_client, priority-sorted)
    all_client_ready = sorted(
        [l for l in unclaimed if l.next_action == "send_to_client"],
        key=_priority_key,
    )
    top_client_ready = [
        DailyClientReadyItem(
            lead_id=l.lead_id,
            name=l.name,
            source=l.source,
            score=l.score,
            rating=l.rating,
            next_action=l.next_action,
        )
        for l in all_client_ready[:_DAILY_CAP]
    ]

    # 4. Followup candidates (outcome = no_answer, unclaimed, score-sorted)
    followup_rows = db.execute(
        """
        SELECT lo.lead_id, l.name, l.source, l.score, lo.recorded_at
        FROM lead_outcomes lo
        JOIN leads l ON l.id = lo.lead_id
        WHERE lo.outcome = 'no_answer'
        ORDER BY l.score DESC, lo.lead_id ASC
        """
    ).fetchall()
    all_followup = [
        r for r in followup_rows if r["lead_id"] not in claimed_ids
    ]
    top_followup = [
        DailyFollowupItem(
            lead_id=r["lead_id"],
            name=r["name"],
            source=r["source"],
            score=r["score"],
            outcome_recorded_at=r["recorded_at"],
        )
        for r in all_followup[:_DAILY_CAP]
    ]

    # 5. Source warnings (review/deprioritize with data_sufficient)
    outcome_rows = db.execute(
        """
        SELECT l.source, lo.outcome, COUNT(*) as cnt
        FROM lead_outcomes lo
        JOIN leads l ON l.id = lo.lead_id
        GROUP BY l.source, lo.outcome
        """
    ).fetchall()
    source_map: dict[str, dict[str, int]] = {}
    for row in outcome_rows:
        src = row["source"]
        if src not in source_map:
            source_map[src] = {v: 0 for v in _OUTCOME_VALUES}
        source_map[src][row["outcome"]] = row["cnt"]
    warnings: list[DailySourceWarning] = []
    for src, counts in sorted(source_map.items()):
        total = sum(counts.values())
        recommendation, rationale, data_sufficient = (
            _source_outcome_recommendation(counts, total)
        )
        if data_sufficient and recommendation in ("review", "deprioritize"):
            warnings.append(
                DailySourceWarning(
                    source=src,
                    recommendation=recommendation,
                    rationale=rationale,
                    total_outcomes=total,
                )
            )

    return DailyActionsResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        summary=DailyActionSummary(
            pending_review=len(all_review),
            client_ready=len(all_client_ready),
            followup_candidates=len(all_followup),
            source_warnings=len(warnings),
        ),
        top_review=top_review,
        top_client_ready=top_client_ready,
        top_followup=top_followup,
        source_warnings=warnings,
    )


# --- Follow-up Handoffs ---


def _followup_instruction(rating: str) -> str:
    if rating == "high":
        return "Retry contact — high-value lead, send personalized follow-up email"
    if rating == "medium":
        return "Retry contact — send a short follow-up email"
    return "Retry contact — send a brief check-in email, consider deprioritizing if no response"


def _followup_message(name: str, rating: str) -> str:
    if rating == "high":
        return (
            f"Hi {name}, I wanted to personally follow up — I think there's a "
            f"strong fit here. Would you have a few minutes to connect this week?"
        )
    if rating == "medium":
        return (
            f"Hi {name}, following up on my previous message. Let me know if "
            f"you're still interested or if there's a better time to connect."
        )
    return (
        f"Hi {name}, just checking in one last time. If now isn't the right "
        f"time, no worries at all."
    )


@router.get(
    "/internal/followup-handoffs",
    response_model=FollowupHandoffResponse,
)
def get_followup_handoffs() -> FollowupHandoffResponse:
    """Action handoff surface for no_answer retry candidates."""
    db = get_db()
    rows = db.execute(
        """
        SELECT lo.lead_id, l.name, l.email, l.source, l.score, lo.recorded_at
        FROM lead_outcomes lo
        JOIN leads l ON l.id = lo.lead_id
        WHERE lo.outcome = 'no_answer'
        ORDER BY l.score DESC, lo.lead_id ASC
        """
    ).fetchall()
    claimed_ids = _get_claimed_lead_ids()
    items: list[FollowupHandoffItem] = []
    for row in rows:
        if row["lead_id"] in claimed_ids:
            continue
        rating = get_rating(row["score"])
        items.append(
            FollowupHandoffItem(
                lead_id=row["lead_id"],
                name=row["name"],
                email=row["email"],
                source=row["source"],
                score=row["score"],
                rating=rating,
                outcome_recorded_at=row["recorded_at"],
                channel="email",
                action="retry_contact",
                instruction=_followup_instruction(rating),
                suggested_message=_followup_message(row["name"], rating),
            )
        )
    return FollowupHandoffResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        total=len(items),
        items=items,
    )


# --- Follow-up Automation ---


@router.get(
    "/internal/followup-automation",
    response_model=FollowupAutomationResponse,
)
def get_followup_automation() -> FollowupAutomationResponse:
    """Machine-consumable follow-up payloads for automation consumers."""
    db = get_db()
    rows = db.execute(
        """
        SELECT lo.lead_id, l.name, l.email, l.source, l.score, lo.recorded_at
        FROM lead_outcomes lo
        JOIN leads l ON l.id = lo.lead_id
        WHERE lo.outcome = 'no_answer'
        ORDER BY l.score DESC, lo.lead_id ASC
        """
    ).fetchall()
    claimed_ids = _get_claimed_lead_ids()
    items: list[FollowupAutomationItem] = []
    for i, row in enumerate(
        r for r in rows if r["lead_id"] not in claimed_ids
    ):
        rating = get_rating(row["score"])
        items.append(
            FollowupAutomationItem(
                lead_id=row["lead_id"],
                channel="email",
                action="retry_contact",
                priority=i,
                payload=FollowupAutomationPayload(
                    name=row["name"],
                    email=row["email"],
                    source=row["source"],
                    score=row["score"],
                    rating=rating,
                    instruction=_followup_instruction(rating),
                    suggested_message=_followup_message(row["name"], rating),
                ),
            )
        )
    return FollowupAutomationResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        total=len(items),
        items=items,
    )


# --- Follow-up Automation CSV Export ---

_FOLLOWUP_CSV_COLUMNS = [
    "lead_id", "to", "subject", "body", "channel", "priority",
    "source", "score", "rating",
]

_FOLLOWUP_SUBJECT_BY_RATING: dict[str, str] = {
    "high": "Following up \u2014 let\u2019s connect this week",
    "medium": "Quick follow-up",
    "low": "Checking in",
}


@router.get(
    "/internal/followup-automation/export.csv",
    response_class=PlainTextResponse,
)
def export_followup_automation_csv(
    source: str | None = None,
    limit: int | None = Query(default=None, ge=1),
) -> PlainTextResponse:
    """CSV export of followup automation items for operator/external-tool use."""
    db = get_db()
    query = """
        SELECT lo.lead_id, l.name, l.email, l.source, l.score
        FROM lead_outcomes lo
        JOIN leads l ON l.id = lo.lead_id
        WHERE lo.outcome = 'no_answer'
    """
    params: list[object] = []
    if source is not None:
        query += " AND l.source = ?"
        params.append(source)
    query += " ORDER BY l.score DESC, lo.lead_id ASC"
    rows = db.execute(query, params).fetchall()
    claimed_ids = _get_claimed_lead_ids()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(_FOLLOWUP_CSV_COLUMNS)
    count = 0
    for i, row in enumerate(r for r in rows if r["lead_id"] not in claimed_ids):
        if limit is not None and count >= limit:
            break
        rating = get_rating(row["score"])
        csv_row = {
            "lead_id": row["lead_id"],
            "to": row["email"],
            "subject": _FOLLOWUP_SUBJECT_BY_RATING.get(rating, "Follow-up"),
            "body": _followup_message(row["name"], rating),
            "channel": "email",
            "priority": i,
            "source": row["source"],
            "score": row["score"],
            "rating": rating,
        }
        writer.writerow(
            [_sanitize_csv_value(csv_row[col]) for col in _FOLLOWUP_CSV_COLUMNS]
        )
        count += 1
    return PlainTextResponse(
        content=output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=followup-automation.csv",
        },
    )


# --- Source Intelligence ---


@router.get(
    "/internal/source-intelligence",
    response_model=SourceIntelligenceResponse,
)
def get_source_intelligence(
    source: str | None = Query(default=None),
) -> SourceIntelligenceResponse:
    """Unified per-source intelligence: leads, scores, actions, outcomes."""
    db = get_db()

    # 1. Per-source lead counts and avg score
    src_filter = ""
    src_params: list[str] = []
    if source is not None:
        src_filter = " WHERE source = ?"
        src_params = [source.strip().lower()]
    lead_rows = db.execute(
        "SELECT source, COUNT(*) AS total, ROUND(AVG(score), 1) AS avg_score "
        f"FROM leads{src_filter} GROUP BY source ORDER BY total DESC",
        src_params,
    ).fetchall()
    lead_map: dict[str, dict] = {
        r["source"]: {"leads": r["total"], "avg_score": r["avg_score"]}
        for r in lead_rows
    }

    # 2. Per-source action counts (reuse _get_actionable_leads)
    actionable = _get_actionable_leads(source)
    action_counts: dict[str, dict[str, int]] = {}
    for lead in actionable:
        counts = action_counts.setdefault(
            lead.source, {"client_ready": 0, "review": 0}
        )
        if lead.next_action == "send_to_client":
            counts["client_ready"] += 1
        elif lead.next_action == "review_manually":
            counts["review"] += 1

    # 3. Per-source outcome counts (reuse source-outcome-actions pattern)
    outcome_filter = ""
    outcome_params: list[str] = []
    if source is not None:
        outcome_filter = " WHERE l.source = ?"
        outcome_params = [source.strip().lower()]
    outcome_rows = db.execute(
        "SELECT l.source, lo.outcome, COUNT(*) as cnt "
        "FROM lead_outcomes lo "
        f"JOIN leads l ON l.id = lo.lead_id{outcome_filter} "
        "GROUP BY l.source, lo.outcome",
        outcome_params,
    ).fetchall()
    outcome_map: dict[str, dict[str, int]] = {}
    for row in outcome_rows:
        src = row["source"]
        if src not in outcome_map:
            outcome_map[src] = {v: 0 for v in _OUTCOME_VALUES}
        outcome_map[src][row["outcome"]] = row["cnt"]

    # 4. Build per-source items
    all_sources = sorted(
        lead_map.keys(), key=lambda s: (-lead_map[s]["leads"], s)
    )
    items: list[SourceIntelligenceItem] = []
    for src in all_sources:
        info = lead_map[src]
        actions = action_counts.get(src, {"client_ready": 0, "review": 0})
        outcomes = outcome_map.get(src, {v: 0 for v in _OUTCOME_VALUES})
        total_outcomes = sum(outcomes.values())
        recommendation, rationale, data_sufficient = (
            _source_outcome_recommendation(outcomes, total_outcomes)
        )
        items.append(
            SourceIntelligenceItem(
                source=src,
                leads=info["leads"],
                avg_score=info["avg_score"],
                pending_review=actions["review"],
                client_ready=actions["client_ready"],
                followup_candidates=outcomes.get("no_answer", 0),
                outcomes=SourceIntelligenceOutcomes(**outcomes),
                recommendation=recommendation,
                rationale=rationale,
                data_sufficient=data_sufficient,
            )
        )

    # 5. Global totals
    total_leads = sum(it.leads for it in items)
    total_avg = (
        round(sum(it.avg_score * it.leads for it in items) / total_leads, 1)
        if total_leads
        else 0.0
    )
    total_outcomes = SourceIntelligenceOutcomes(
        contacted=sum(it.outcomes.contacted for it in items),
        qualified=sum(it.outcomes.qualified for it in items),
        won=sum(it.outcomes.won for it in items),
        lost=sum(it.outcomes.lost for it in items),
        no_answer=sum(it.outcomes.no_answer for it in items),
        bad_fit=sum(it.outcomes.bad_fit for it in items),
    )
    totals = SourceIntelligenceTotals(
        leads=total_leads,
        avg_score=total_avg,
        pending_review=sum(it.pending_review for it in items),
        client_ready=sum(it.client_ready for it in items),
        followup_candidates=sum(it.followup_candidates for it in items),
        outcomes=total_outcomes,
    )

    return SourceIntelligenceResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        total_sources=len(items),
        totals=totals,
        by_source=items,
    )
