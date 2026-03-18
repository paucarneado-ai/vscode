from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query

from apps.api.auth import require_api_key
from apps.api.services.actions import ACTION_PRIORITY
from apps.api.services.operational import get_actionable_leads as _get_actionable_leads
from apps.api.schemas import LeadOperationalSummary, QueueResponse

router = APIRouter(dependencies=[Depends(require_api_key)])


_STATUS_RANK = {"new": 0, "contacted": 1}


def _priority_key(lead: LeadOperationalSummary) -> tuple[int, int, int, int]:
    """Sort key: alert DESC, status (new first), action priority ASC, score DESC."""
    alert_rank = 0 if lead.alert else 1
    status_rank = _STATUS_RANK.get(lead.status, 2)
    try:
        action_rank = ACTION_PRIORITY.index(lead.next_action)
    except ValueError:
        action_rank = len(ACTION_PRIORITY)
    return (alert_rank, status_rank, action_rank, -lead.score)


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
