from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from apps.api.db import get_db
from apps.api.schemas import (
    LeadCreate,
    LeadCreateResult,
    LeadDeliveryResponse,
    LeadPackResponse,
    LeadResponse,
)
from apps.api.services.leadpack import build_summary, get_rating, render_lead_pack_html
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


@router.get("/leads/{lead_id}/pack", response_model=LeadPackResponse)
def get_lead_pack(lead_id: int) -> LeadPackResponse:
    db = get_db()
    row = db.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    lead = dict(row)
    rating = get_rating(lead["score"])
    summary = build_summary(lead["name"], lead["source"], lead["score"], rating)
    return LeadPackResponse(
        lead_id=lead["id"],
        created_at=lead["created_at"],
        name=lead["name"],
        email=lead["email"],
        source=lead["source"],
        notes=lead["notes"],
        score=lead["score"],
        rating=rating,
        summary=summary,
    )


@router.get("/leads/{lead_id}/pack/html", response_class=HTMLResponse)
def get_lead_pack_html(lead_id: int) -> HTMLResponse:
    pack = get_lead_pack(lead_id)
    return HTMLResponse(content=render_lead_pack_html(pack))


@router.get("/leads/{lead_id}/delivery", response_model=LeadDeliveryResponse)
def get_lead_delivery(lead_id: int) -> LeadDeliveryResponse:
    pack = get_lead_pack(lead_id)
    return LeadDeliveryResponse(
        lead_id=pack.lead_id,
        delivery_status="generated",
        channel="api",
        generated_at=pack.created_at,
        pack=pack,
        message="Lead pack generated and ready for delivery",
    )
