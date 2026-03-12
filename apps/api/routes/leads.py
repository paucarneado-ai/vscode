from fastapi import APIRouter

from apps.api.schemas import LeadCreate, LeadCreateResult, LeadResponse
from apps.api.services.scoring import calculate_lead_score


router = APIRouter()


@router.post("/leads", response_model=LeadCreateResult)
def create_lead(payload: LeadCreate) -> LeadCreateResult:
    score = calculate_lead_score(payload.source, payload.notes)

    lead = LeadResponse(
        **payload.model_dump(),
        score=score,
    )

    return LeadCreateResult(
        message="lead received",
        lead=lead,
        meta={"version": "v1", "status": "accepted"},
    )