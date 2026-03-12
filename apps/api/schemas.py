from pydantic import BaseModel, EmailStr, Field


class LeadCreate(BaseModel):
    name: str = Field(min_length=1)
    email: EmailStr
    source: str = Field(min_length=1)
    notes: str | None = None


class LeadResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    source: str
    notes: str | None = None
    score: int
    created_at: str


class LeadCreateResult(BaseModel):
    message: str
    lead: LeadResponse
    meta: dict[str, str]