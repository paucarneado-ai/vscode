import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

from apps.api.db import get_db
from collections import defaultdict

from apps.api.schemas import (
    LeadCreate,
    LeadCreateResult,
    LeadDeliveryResponse,
    LeadOperationalSummary,
    LeadPackResponse,
    LeadResponse,
    WebhookLeadPayload,
    WorklistGroup,
    WorklistResponse,
)
from apps.api.services.leadpack import (
    build_summary,
    get_rating,
    render_lead_pack_html,
    render_lead_pack_text,
)
from apps.api.services.actions import determine_next_action, get_instruction, should_alert
from apps.api.services.scoring import calculate_lead_score


router = APIRouter()


def _create_lead_internal(payload: LeadCreate) -> tuple[LeadCreateResult, int]:
    """Create a lead and return (result, http_status)."""
    source = payload.source.strip().lower()
    if not source:
        raise HTTPException(status_code=422, detail="source cannot be empty or whitespace-only")
    email = payload.email.strip().lower()

    db = get_db()
    existing = db.execute(
        "SELECT * FROM leads WHERE email = ? AND source = ?", (email, source)
    ).fetchone()
    if existing is not None:
        lead = LeadResponse(**dict(existing))
        result = LeadCreateResult(
            message="lead already exists",
            lead=lead,
            meta={"version": "v1", "status": "duplicate"},
        )
        return result, 409

    score = calculate_lead_score(source, payload.notes)

    cursor = db.execute(
        "INSERT INTO leads (name, email, source, notes, score) VALUES (?, ?, ?, ?, ?)",
        (payload.name, email, source, payload.notes, score),
    )
    db.commit()

    row = db.execute("SELECT * FROM leads WHERE id = ?", (cursor.lastrowid,)).fetchone()
    lead = LeadResponse(**dict(row))

    result = LeadCreateResult(
        message="lead received",
        lead=lead,
        meta={"version": "v1", "status": "accepted"},
    )
    return result, 200


@router.post("/leads", response_model=LeadCreateResult)
def create_lead(payload: LeadCreate) -> LeadCreateResult:
    result, status = _create_lead_internal(payload)
    if status == 409:
        return JSONResponse(status_code=409, content=result.model_dump())
    return result


@router.post("/leads/ingest")
def ingest_leads(items: list[LeadCreate]) -> dict:
    created = 0
    duplicates = 0
    errors: list[dict] = []

    for i, item in enumerate(items):
        try:
            _, status = _create_lead_internal(item)
            if status == 200:
                created += 1
            elif status == 409:
                duplicates += 1
        except Exception as exc:
            errors.append({"index": i, "email": item.email, "error": str(exc)})

    return {
        "total": len(items),
        "created": created,
        "duplicates": duplicates,
        "errors": errors,
    }


@router.post("/leads/webhook/{provider}")
def webhook_ingest(provider: str, payload: WebhookLeadPayload) -> dict:
    provider_clean = provider.strip().lower()
    if not provider_clean:
        raise HTTPException(status_code=422, detail="provider cannot be empty or whitespace-only")
    source = f"webhook:{provider_clean}"
    lead_create = LeadCreate(
        name=payload.name, email=payload.email, source=source, notes=payload.notes
    )
    result, status = _create_lead_internal(lead_create)
    if status == 409:
        return JSONResponse(
            status_code=409,
            content={"status": "duplicate", "lead_id": result.lead.id},
        )
    return {"status": "accepted", "lead_id": result.lead.id}


def _build_where_clause(
    source: str | None = None,
    min_score: int | None = None,
    q: str | None = None,
) -> tuple[str, list[str | int]]:
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

    clause = " WHERE " + " AND ".join(conditions) if conditions else ""
    return clause, params


def _build_leads_query(
    source: str | None = None,
    min_score: int | None = None,
    limit: int | None = None,
    offset: int | None = None,
    q: str | None = None,
) -> tuple[str, list[str | int]]:
    where, params = _build_where_clause(source, min_score, q)
    query = "SELECT * FROM leads" + where + " ORDER BY id DESC"

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
def get_leads_summary(
    source: str | None = None,
    min_score: int | None = Query(default=None, ge=0),
    q: str | None = None,
) -> dict:
    db = get_db()
    where, params = _build_where_clause(source, min_score, q)

    row = db.execute(
        f"SELECT COUNT(*) AS total, COALESCE(AVG(score), 0) AS avg_score FROM leads{where}",
        params,
    ).fetchone()
    total_leads = row["total"]
    average_score = round(row["avg_score"], 1)

    bucket_row = db.execute(
        f"SELECT"
        f" SUM(CASE WHEN score < 40 THEN 1 ELSE 0 END) AS low,"
        f" SUM(CASE WHEN score >= 40 AND score < 60 THEN 1 ELSE 0 END) AS medium,"
        f" SUM(CASE WHEN score >= 60 THEN 1 ELSE 0 END) AS high"
        f" FROM leads{where}",
        params,
    ).fetchone()
    low_score_count = bucket_row["low"] or 0
    medium_score_count = bucket_row["medium"] or 0
    high_score_count = bucket_row["high"] or 0

    source_rows = db.execute(
        f"SELECT source, COUNT(*) AS cnt FROM leads{where} GROUP BY source ORDER BY cnt DESC",
        params,
    ).fetchall()
    counts_by_source = {r["source"]: r["cnt"] for r in source_rows}

    return {
        "total_leads": total_leads,
        "average_score": average_score,
        "low_score_count": low_score_count,
        "medium_score_count": medium_score_count,
        "high_score_count": high_score_count,
        "counts_by_source": counts_by_source,
    }


def _get_actionable_leads(
    source: str | None = None,
    limit: int | None = None,
) -> list[LeadOperationalSummary]:
    """Return actionable leads as LeadOperationalSummary list."""
    db = get_db()
    conditions: list[str] = [
        "(score >= 40 OR (notes IS NOT NULL AND TRIM(notes) != ''))"
    ]
    params: list[str | int] = []
    if source is not None:
        conditions.append("source = ?")
        params.append(source)
    where = " WHERE " + " AND ".join(conditions)
    query = f"SELECT * FROM leads{where} ORDER BY score DESC"
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)
    rows = db.execute(query, params).fetchall()
    now = datetime.now(timezone.utc).isoformat()
    results = []
    for row in rows:
        lead = dict(row)
        rating = get_rating(lead["score"])
        next_action = determine_next_action(lead["score"], lead["notes"])
        results.append(LeadOperationalSummary(
            lead_id=lead["id"],
            source=lead["source"],
            score=lead["score"],
            rating=rating,
            next_action=next_action,
            instruction=get_instruction(next_action),
            alert=should_alert(lead["score"]),
            summary=build_summary(lead["name"], lead["source"], lead["score"], rating),
            generated_at=now,
        ))
    return results


@router.get("/leads/actionable", response_model=list[LeadOperationalSummary])
def get_actionable_leads(
    source: str | None = None,
    limit: int | None = Query(default=None, ge=1),
) -> list[LeadOperationalSummary]:
    return _get_actionable_leads(source, limit)


ACTION_PRIORITY = ["send_to_client", "review_manually", "request_more_info", "enrich_first"]


@router.get("/leads/actionable/worklist", response_model=WorklistResponse)
def get_actionable_worklist(
    source: str | None = None,
    limit: int | None = Query(default=None, ge=1),
) -> WorklistResponse:
    leads = _get_actionable_leads(source, limit)
    grouped: dict[str, list[LeadOperationalSummary]] = defaultdict(list)
    for lead in leads:
        grouped[lead.next_action].append(lead)
    priority_set = set(ACTION_PRIORITY)
    ordered_actions = [a for a in ACTION_PRIORITY if a in grouped]
    ordered_actions += [a for a in grouped if a not in priority_set]
    groups = [
        WorklistGroup(next_action=action, count=len(grouped[action]), leads=grouped[action])
        for action in ordered_actions
    ]
    return WorklistResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        total=len(leads),
        groups=groups,
    )


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
    next_action = determine_next_action(lead["score"], lead["notes"])
    alert = should_alert(lead["score"])
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
        next_action=next_action,
        alert=alert,
    )


@router.get("/leads/{lead_id}/pack/html", response_class=HTMLResponse)
def get_lead_pack_html(lead_id: int) -> HTMLResponse:
    pack = get_lead_pack(lead_id)
    return HTMLResponse(content=render_lead_pack_html(pack))


@router.get("/leads/{lead_id}/pack.txt", response_class=PlainTextResponse)
def get_lead_pack_text(lead_id: int) -> PlainTextResponse:
    pack = get_lead_pack(lead_id)
    return PlainTextResponse(content=render_lead_pack_text(pack))


@router.get("/leads/{lead_id}/operational", response_model=LeadOperationalSummary)
def get_lead_operational(lead_id: int) -> LeadOperationalSummary:
    pack = get_lead_pack(lead_id)
    return LeadOperationalSummary(
        lead_id=pack.lead_id,
        source=pack.source,
        score=pack.score,
        rating=pack.rating,
        next_action=pack.next_action,
        instruction=get_instruction(pack.next_action),
        alert=pack.alert,
        summary=pack.summary,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/leads/{lead_id}/delivery", response_model=LeadDeliveryResponse)
def get_lead_delivery(lead_id: int) -> LeadDeliveryResponse:
    pack = get_lead_pack(lead_id)
    generated_at = datetime.now(timezone.utc).isoformat()
    if pack.alert:
        message = f"ALERT: lead requires attention — {pack.next_action}"
    else:
        message = f"Lead pack generated — next: {pack.next_action}"
    return LeadDeliveryResponse(
        lead_id=pack.lead_id,
        delivery_status="generated",
        channel="api",
        generated_at=generated_at,
        next_action=pack.next_action,
        alert=pack.alert,
        pack=pack,
        message=message,
    )
