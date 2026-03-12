from fastapi import APIRouter, HTTPException

from apps.api.db import get_db
from apps.api.schemas import LeadCreate, LeadCreateResult, LeadResponse
from apps.api.services.scoring import calculate_lead_score


router = APIRouter()


@router.post("/leads", response_model=LeadCreateResult)
def create_lead(payload: LeadCreate) -> LeadCreateResult:
    score = calculate_lead_score(payload.source, payload.notes)
    db = get_db()

    cursor = db.execute(
        "INSERT INTO leads (name, email, source, notes, score) VALUES (?, ?, ?, ?, ?)",
        (payload.name, payload.email, payload.source, payload.notes, score),
    )
    db.commit()

    row = db.execute("SELECT * FROM leads WHERE id = ?", (cursor.lastrowid,)).fetchone()
    lead = LeadResponse(**dict(row))

    return LeadCreateResult(
        message="lead received",
        lead=lead,
        meta={"version": "v1", "status": "accepted"},
    )


@router.get("/leads", response_model=list[LeadResponse])
def list_leads() -> list[LeadResponse]:
    db = get_db()
    rows = db.execute("SELECT * FROM leads ORDER BY id DESC").fetchall()
    return [LeadResponse(**dict(row)) for row in rows]


@router.get("/leads/{lead_id}", response_model=LeadResponse)
def get_lead(lead_id: int) -> LeadResponse:
    db = get_db()
    row = db.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    return LeadResponse(**dict(row))
