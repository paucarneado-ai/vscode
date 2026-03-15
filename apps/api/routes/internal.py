from datetime import datetime, timezone

from fastapi import APIRouter, Query

from apps.api.db import get_db
from apps.api.routes.leads import _get_actionable_leads, get_lead_pack
from apps.api.services.actions import ACTION_PRIORITY
from apps.api.schemas import (
    AutomationBatchResponse,
    AutomationDispatch,
    ClaimRequest,
    ClaimResponse,
    LeadOperationalSummary,
    QueueResponse,
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
    if limit is not None:
        sorted_leads = sorted_leads[:limit]
    return QueueResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        total=len(sorted_leads),
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
    return ClaimResponse(claimed=claimed, already_claimed=already_claimed, not_found=not_found)


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
        total=len(items),
        items=items,
    )
