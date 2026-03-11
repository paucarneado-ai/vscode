from fastapi import APIRouter
from pydantic import BaseModel, EmailStr


router = APIRouter(prefix="/leads", tags=["leads"])


class LeadCreate(BaseModel):
    name: str
    email: EmailStr
    source: str
    notes: str | None = None


@router.post("")
def create_lead(payload: LeadCreate) -> dict:
    return {
        "message": "lead received",
        "lead": payload.model_dump(),
    }