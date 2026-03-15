import csv
import io
import json
import re
import sqlite3
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

from apps.api.db import get_db
from collections import defaultdict

from apps.api.schemas import (
    ExternalLeadPayload,
    ExternalLeadResult,
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
from apps.api.services.actions import ACTION_PRIORITY, determine_next_action, get_instruction, should_alert
from apps.api.services.scoring import calculate_lead_score


router = APIRouter()

_CANONICAL_SOURCE_RE = re.compile(r"^[a-z0-9]+:[a-z0-9][a-z0-9_-]*$")
_PROVIDER_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _validate_provider(provider: str) -> str:
    """Normalize and validate webhook provider. Returns cleaned value or raises 422."""
    clean = provider.strip().lower()
    if not clean:
        raise HTTPException(status_code=422, detail="provider cannot be empty or whitespace-only")
    if not _PROVIDER_RE.match(clean):
        raise HTTPException(
            status_code=422,
            detail="provider must contain only lowercase letters, digits, hyphens and underscores",
        )
    return clean


def _create_lead_internal(payload: LeadCreate) -> tuple[LeadCreateResult, int]:
    """Create a lead and return (result, http_status)."""
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="name cannot be empty or whitespace-only")
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

    try:
        cursor = db.execute(
            "INSERT INTO leads (name, email, source, notes, score) VALUES (?, ?, ?, ?, ?)",
            (name, email, source, payload.notes, score),
        )
        db.commit()
    except sqlite3.IntegrityError:
        # Race condition: concurrent insert beat the SELECT check above.
        # Re-fetch the existing lead and return duplicate response.
        existing = db.execute(
            "SELECT * FROM leads WHERE email = ? AND source = ?", (email, source)
        ).fetchone()
        lead = LeadResponse(**dict(existing))
        return LeadCreateResult(
            message="lead already exists",
            lead=lead,
            meta={"version": "v1", "status": "duplicate"},
        ), 409

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
    provider_clean = _validate_provider(provider)
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


@router.post("/leads/webhook/{provider}/batch")
def webhook_ingest_batch(provider: str, items: list[WebhookLeadPayload]) -> dict:
    provider_clean = _validate_provider(provider)
    source = f"webhook:{provider_clean}"

    created = 0
    duplicates = 0
    errors: list[dict] = []

    for i, item in enumerate(items):
        try:
            lead_create = LeadCreate(
                name=item.name, email=item.email, source=source, notes=item.notes
            )
            _, status = _create_lead_internal(lead_create)
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


def _build_external_notes(
    notes: str | None,
    phone: str | None,
    metadata: dict[str, Any] | None,
) -> str | None:
    """Serialize phone/metadata into notes using @ext: format."""
    ext_fields: dict[str, Any] = {}
    if metadata:
        ext_fields.update(metadata)
    if phone is not None:
        phone = phone.strip()
    if phone:
        ext_fields["phone"] = phone

    if not ext_fields:
        return notes

    ext_line = "@ext:" + json.dumps(ext_fields, ensure_ascii=False, separators=(",", ":"))

    if notes and notes.strip():
        return notes.strip() + "\n\n" + ext_line
    return ext_line


@router.post("/leads/external", response_model=ExternalLeadResult)
def external_ingest(payload: ExternalLeadPayload) -> ExternalLeadResult:
    """Canonical adapter for external integrations (forms, landings, n8n, etc.)."""
    source_normalized = payload.source.strip().lower()
    if not _CANONICAL_SOURCE_RE.match(source_normalized):
        raise HTTPException(
            status_code=422,
            detail="source must follow 'type:identifier' format (e.g. 'landing:barcos-venta', 'n8n:captacion')",
        )
    merged_notes = _build_external_notes(payload.notes, payload.phone, payload.metadata)
    lead_create = LeadCreate(
        name=payload.name,
        email=payload.email,
        source=payload.source,
        notes=merged_notes,
    )
    result, status = _create_lead_internal(lead_create)
    return JSONResponse(
        status_code=status if status == 409 else 200,
        content=ExternalLeadResult(
            status=result.meta["status"],
            lead_id=result.lead.id,
            score=result.lead.score,
            message=result.message,
        ).model_dump(),
    )


def _build_where_clause(
    source: str | None = None,
    min_score: int | None = None,
    q: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
) -> tuple[str, list[str | int]]:
    conditions: list[str] = []
    params: list[str | int] = []

    if source is not None:
        conditions.append("source = ?")
        params.append(source.strip().lower())
    if min_score is not None:
        conditions.append("score >= ?")
        params.append(min_score)
    if q is not None:
        q = q.strip()
    if q:
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        conditions.append("(name LIKE ? ESCAPE '\\' OR email LIKE ? ESCAPE '\\' OR notes LIKE ? ESCAPE '\\')")
        params.extend([pattern, pattern, pattern])

    if created_from is not None:
        created_from = created_from.strip()
    if created_from:
        if not _DATE_RE.match(created_from):
            raise HTTPException(status_code=422, detail="created_from must be YYYY-MM-DD")
        conditions.append("created_at >= ?")
        params.append(created_from)
    if created_to is not None:
        created_to = created_to.strip()
    if created_to:
        if not _DATE_RE.match(created_to):
            raise HTTPException(status_code=422, detail="created_to must be YYYY-MM-DD")
        conditions.append("created_at <= ? || ' 23:59:59'")
        params.append(created_to)

    clause = " WHERE " + " AND ".join(conditions) if conditions else ""
    return clause, params


def _build_leads_query(
    source: str | None = None,
    min_score: int | None = None,
    limit: int | None = None,
    offset: int | None = None,
    q: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
) -> tuple[str, list[str | int]]:
    where, params = _build_where_clause(source, min_score, q, created_from, created_to)
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
    created_from: str | None = None,
    created_to: str | None = None,
) -> list[LeadResponse]:
    db = get_db()
    query, params = _build_leads_query(source, min_score, limit, offset, q, created_from, created_to)
    rows = db.execute(query, params).fetchall()
    return [LeadResponse(**dict(row)) for row in rows]


@router.get("/leads/sources")
def list_sources() -> list[str]:
    db = get_db()
    rows = db.execute("SELECT DISTINCT source FROM leads ORDER BY source").fetchall()
    return [row["source"] for row in rows]


@router.get("/leads/summary")
def get_leads_summary(
    source: str | None = None,
    min_score: int | None = Query(default=None, ge=0),
    q: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
) -> dict:
    db = get_db()
    where, params = _build_where_clause(source, min_score, q, created_from, created_to)

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
        params.append(source.strip().lower())
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
            name=lead["name"],
            source=lead["source"],
            score=lead["score"],
            rating=rating,
            next_action=next_action,
            instruction=get_instruction(next_action),
            alert=should_alert(lead["score"]),
            summary=build_summary(lead["name"], lead["source"], lead["score"], rating),
            created_at=lead["created_at"],
            generated_at=now,
        ))
    return results


@router.get("/leads/actionable", response_model=list[LeadOperationalSummary])
def get_actionable_leads(
    source: str | None = None,
    limit: int | None = Query(default=None, ge=1),
) -> list[LeadOperationalSummary]:
    return _get_actionable_leads(source, limit)


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
_CSV_DANGEROUS_PREFIXES = ("=", "+", "-", "@")


def _sanitize_csv_value(value: Any) -> Any:
    """Prefix dangerous string values to prevent CSV injection in spreadsheets."""
    if isinstance(value, str) and value and value[0] in _CSV_DANGEROUS_PREFIXES:
        return "'" + value
    return value


@router.get("/leads/export.csv", response_class=PlainTextResponse)
def export_leads_csv(
    source: str | None = None,
    min_score: int | None = Query(default=None, ge=0),
    limit: int | None = Query(default=None, ge=1),
    offset: int | None = Query(default=None, ge=0),
    q: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
) -> PlainTextResponse:
    db = get_db()
    query, params = _build_leads_query(source, min_score, limit, offset, q, created_from, created_to)
    rows = db.execute(query, params).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(CSV_COLUMNS)
    for row in rows:
        d = dict(row)
        writer.writerow([_sanitize_csv_value(d[col]) for col in CSV_COLUMNS])

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
        name=pack.name,
        source=pack.source,
        score=pack.score,
        rating=pack.rating,
        next_action=pack.next_action,
        instruction=get_instruction(pack.next_action),
        alert=pack.alert,
        summary=pack.summary,
        created_at=pack.created_at,
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
