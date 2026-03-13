from datetime import datetime, timezone

from fastapi import APIRouter, Query

from apps.api.routes.leads import ACTION_PRIORITY, _get_actionable_leads
from apps.api.schemas import LeadOperationalSummary, QueueResponse

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
    leads = _get_actionable_leads(source, limit)
    sorted_leads = sorted(leads, key=_priority_key)
    urgent_count = sum(1 for lead in leads if lead.alert)
    return QueueResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        total=len(sorted_leads),
        urgent_count=urgent_count,
        items=sorted_leads,
    )
