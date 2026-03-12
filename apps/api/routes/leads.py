import csv
import io

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

from apps.api.db import get_db
from apps.api.schemas import (
    LeadCreate,
    LeadCreateResult,
    LeadDeliveryResponse,
    LeadPackResponse,
    LeadResponse,
)
from apps.api.services.leadpack import (
    build_summary,
    get_rating,
    render_lead_pack_html,
    render_lead_pack_text,
)
from apps.api.services.scoring import calculate_lead_score


router = APIRouter()


@router.post("/leads", response_model=LeadCreateResult)
def create_lead(payload: LeadCreate) -> LeadCreateResult:
    source = payload.source.strip().lower()
    email = payload.email.strip().lower()

    db = get_db()
    existing = db.execute(
        "SELECT * FROM leads WHERE email = ? AND source = ?", (email, source)
    ).fetchone()
    if existing is not None:
        lead = LeadResponse(**dict(existing))
        body = LeadCreateResult(
            message="lead already exists",
            lead=lead,
            meta={"version": "v1", "status": "duplicate"},
        )
        return JSONResponse(status_code=409, content=body.model_dump())

    score = calculate_lead_score(source, payload.notes)

    cursor = db.execute(
        "INSERT INTO leads (name, email, source, notes, score) VALUES (?, ?, ?, ?, ?)",
        (payload.name, email, source, payload.notes, score),
    )
    db.commit()

    row = db.execute("SELECT * FROM leads WHERE id = ?", (cursor.lastrowid,)).fetchone()
    lead = LeadResponse(**dict(row))

    return LeadCreateResult(
        message="lead received",
        lead=lead,
        meta={"version": "v1", "status": "accepted"},
    )


def _build_leads_query(
    source: str | None = None,
    min_score: int | None = None,
    limit: int | None = None,
    offset: int | None = None,
    q: str | None = None,
) -> tuple[str, list[str | int]]:
    query = "SELECT * FROM leads"
    conditions: list[str] = []
    params: list[str | int] = []

    if source is not None:
        conditions.append("source = ?")
        params.append(source)
    if min_score is not None:
        conditions.append("score >= ?")
        params.append(min_score)
    if q is not None:
        pattern = f"%{q}%"
        conditions.append("(name LIKE ? OR email LIKE ? OR notes LIKE ?)")
        params.extend([pattern, pattern, pattern])

    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY id DESC"

    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)
    if offset is not None:
        if limit is None:
            query += " LIMIT -1"
        query += " OFFSET ?"
        params.append(offset)

    return query, params


@router.get("/leads", response_model=list[LeadResponse])
def list_leads(
    source: str | None = None,
    min_score: int | None = Query(default=None, ge=0),
    limit: int | None = Query(default=None, ge=1),
    offset: int | None = Query(default=None, ge=0),
    q: str | None = None,
) -> list[LeadResponse]:
    db = get_db()
    query, params = _build_leads_query(source, min_score, limit, offset, q)
    rows = db.execute(query, params).fetchall()
    return [LeadResponse(**dict(row)) for row in rows]


@router.get("/leads/summary")
def get_leads_summary() -> dict:
    db = get_db()

    row = db.execute(
        "SELECT COUNT(*) AS total, COALESCE(AVG(score), 0) AS avg_score FROM leads"
    ).fetchone()
    total_leads = row["total"]
    average_score = round(row["avg_score"], 1)

    high_score_row = db.execute(
        "SELECT COUNT(*) AS cnt FROM leads WHERE score >= 60"
    ).fetchone()
    high_score_count = high_score_row["cnt"]

    source_rows = db.execute(
        "SELECT source, COUNT(*) AS cnt FROM leads GROUP BY source ORDER BY cnt DESC"
    ).fetchall()
    counts_by_source = {r["source"]: r["cnt"] for r in source_rows}

    return {
        "total_leads": total_leads,
        "average_score": average_score,
        "high_score_count": high_score_count,
        "counts_by_source": counts_by_source,
    }


CSV_COLUMNS = ["id", "name", "email", "source", "score", "notes"]


@router.get("/leads/export.csv", response_class=PlainTextResponse)
def export_leads_csv(
    source: str | None = None,
    min_score: int | None = Query(default=None, ge=0),
    limit: int | None = Query(default=None, ge=1),
    offset: int | None = Query(default=None, ge=0),
    q: str | None = None,
) -> PlainTextResponse:
    db = get_db()
    query, params = _build_leads_query(source, min_score, limit, offset, q)
    rows = db.execute(query, params).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(CSV_COLUMNS)
    for row in rows:
        d = dict(row)
        writer.writerow([d[col] for col in CSV_COLUMNS])

    return PlainTextResponse(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=leads.csv"},
    )


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


@router.get("/leads/{lead_id}/pack.txt", response_class=PlainTextResponse)
def get_lead_pack_text(lead_id: int) -> PlainTextResponse:
    pack = get_lead_pack(lead_id)
    return PlainTextResponse(content=render_lead_pack_text(pack))


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
