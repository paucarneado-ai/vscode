from pydantic import BaseModel, EmailStr, Field


class LeadCreate(BaseModel):
    name: str = Field(min_length=1)
    email: EmailStr
    source: str = Field(min_length=1)
    notes: str | None = None


VALID_LEAD_STATUSES = {"new", "contacted", "closed", "not_interested"}


class LeadResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    source: str
    notes: str | None = None
    score: int
    status: str = "new"
    created_at: str


class LeadCreateResult(BaseModel):
    message: str
    lead: LeadResponse
    meta: dict[str, str]


class LeadPackResponse(BaseModel):
    lead_id: int
    created_at: str
    name: str
    email: EmailStr
    source: str
    notes: str | None = None
    score: int
    status: str = "new"
    rating: str
    summary: str
    next_action: str
    alert: bool


class WebhookLeadPayload(BaseModel):
    name: str = Field(min_length=1)
    email: EmailStr
    notes: str | None = None


class WebIntakePayload(BaseModel):
    nombre: str = Field(min_length=1)
    email: EmailStr
    telefono: str | None = None
    interes: str | None = None
    mensaje: str | None = None
    origen: str | None = None


class LeadOperationalSummary(BaseModel):
    lead_id: int
    name: str
    email: str
    source: str
    score: int
    status: str = "new"
    rating: str
    next_action: str
    instruction: str
    priority_reason: str
    alert: bool
    summary: str
    phone: str | None = None
    created_at: str
    generated_at: str


class LeadStatusUpdate(BaseModel):
    status: str = Field(min_length=1)


class WorklistGroup(BaseModel):
    next_action: str
    count: int
    leads: list[LeadOperationalSummary]


class WorklistResponse(BaseModel):
    generated_at: str
    total: int
    groups: list[WorklistGroup]


class QueueResponse(BaseModel):
    generated_at: str
    total: int
    urgent_count: int
    items: list[LeadOperationalSummary]


class LeadDeliveryResponse(BaseModel):
    lead_id: int
    delivery_status: str
    channel: str
    generated_at: str
    next_action: str
    alert: bool
    pack: LeadPackResponse
    message: str