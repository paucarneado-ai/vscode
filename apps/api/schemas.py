from pydantic import BaseModel, EmailStr, Field


class LeadCreate(BaseModel):
    name: str = Field(min_length=1)
    email: EmailStr
    source: str = Field(min_length=1)
    notes: str | None = None