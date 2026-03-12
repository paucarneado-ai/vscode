from pydantic import BaseModel, EmailStr, Field


class LeadCreate(BaseModel):
    name: str = Field(min_length=1)
    email: EmailStr
    source: str = Field(min_length=1)
    notes: str | None = None


class LeadResponse(BaseModel):
    name: str
    email: EmailStr
    source: str
    notes: str | None = None
    score: int


class LeadCreateResult(BaseModel):
    message: str
    lead: LeadResponse
    meta: dict[str, str]