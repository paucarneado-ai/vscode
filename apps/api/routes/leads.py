from fastapi import APIRouter

from apps.api.schemas import LeadCreate


router = APIRouter()


@router.post("/leads")
def create_lead(payload: LeadCreate) -> dict:
    return {
        "message": "lead received",
        "lead": payload.model_dump(),
    }