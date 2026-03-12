from fastapi import APIRouter

from apps.api.schemas import LeadCreate, LeadCreateResult, LeadResponse


router = APIRouter()


@router.post("/leads", response_model=LeadCreateResult)
def create_lead(payload: LeadCreate) -> LeadCreateResult:
    lead = LeadResponse(**payload.model_dump())

    return LeadCreateResult(
        message="lead received",
        lead=lead,
        meta={"version": "v1", "status": "accepted"},
    )