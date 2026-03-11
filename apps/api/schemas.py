from pydantic import BaseModel, EmailStr


class LeadCreate(BaseModel):
    name: str
    email: EmailStr
    source: str
    notes: str | None = None