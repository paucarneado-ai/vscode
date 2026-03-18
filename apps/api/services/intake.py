"""Lead intake, normalization, and query service.

Normalization helpers live here so routes stay thin HTTP handlers.
Each provider surface (web form, webhook, batch) has a normalizer
that produces a clean LeadCreate for the shared create_lead path.
"""

from apps.api.db import get_db
from apps.api.schemas import LeadCreate, LeadCreateResult, LeadResponse, VALID_LEAD_STATUSES, WebIntakePayload, WebhookLeadPayload
from apps.api.services.scoring import calculate_lead_score


class SourceValidationError(Exception):
    """Raised when source is empty or whitespace-only after normalization."""


class ProviderValidationError(Exception):
    """Raised when provider name is empty or whitespace-only."""


# --- Normalization helpers ---

def normalize_web_intake(payload: WebIntakePayload) -> LeadCreate:
    """Normalize a web form submission into a LeadCreate.

    Assembles structured notes from optional fields (telefono, interes, mensaje).
    Derives source from origen field with fallback to 'web:sentyacht'.
    """
    source = (payload.origen or "web:sentyacht").strip().lower() or "web:sentyacht"

    notes_lines = []
    if payload.telefono:
        notes_lines.append(f"Teléfono: {payload.telefono}")
    if payload.interes:
        notes_lines.append(f"Interés: {payload.interes}")
    if payload.mensaje:
        notes_lines.append(f"Mensaje: {payload.mensaje}")
    notes = "\n".join(notes_lines) if notes_lines else None

    return LeadCreate(name=payload.nombre, email=payload.email, source=source, notes=notes)


def normalize_webhook_payload(provider: str, payload: WebhookLeadPayload) -> LeadCreate:
    """Normalize a webhook/provider payload into a LeadCreate.

    Validates and cleans the provider name, constructs source as 'webhook:{provider}'.
    Passes notes through as-is (provider/n8n is responsible for structuring notes).
    """
    provider_clean = provider.strip().lower()
    if not provider_clean:
        raise ProviderValidationError("provider cannot be empty or whitespace-only")
    source = f"webhook:{provider_clean}"
    return LeadCreate(name=payload.name, email=payload.email, source=source, notes=payload.notes)


def create_lead(payload: LeadCreate) -> tuple[LeadCreateResult, int]:
    """Create a lead and return (result, http_status).

    Normalizes source/email, checks for duplicates, scores, and persists.
    Returns 200 for new leads, 409 for duplicates.
    Raises SourceValidationError if source is empty after strip.
    """
    source = payload.source.strip().lower()
    if not source:
        raise SourceValidationError("source cannot be empty or whitespace-only")
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


def build_where_clause(
    source: str | None = None,
    min_score: int | None = None,
    q: str | None = None,
    status: str | None = None,
) -> tuple[str, list[str | int]]:
    """Build a WHERE clause for leads queries with bind params."""
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
    if status is not None:
        if status not in VALID_LEAD_STATUSES:
            raise InvalidStatusError(f"Invalid status filter '{status}'. Must be one of: {', '.join(sorted(VALID_LEAD_STATUSES))}")
        conditions.append("status = ?")
        params.append(status)

    clause = " WHERE " + " AND ".join(conditions) if conditions else ""
    return clause, params


def build_leads_query(
    source: str | None = None,
    min_score: int | None = None,
    limit: int | None = None,
    offset: int | None = None,
    q: str | None = None,
    status: str | None = None,
) -> tuple[str, list[str | int]]:
    """Build a full SELECT query for leads with filters, ordering, pagination."""
    where, params = build_where_clause(source, min_score, q, status)
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


def query_leads(
    source: str | None = None,
    min_score: int | None = None,
    limit: int | None = None,
    offset: int | None = None,
    q: str | None = None,
    status: str | None = None,
) -> list[LeadResponse]:
    """Query leads with filters and return as LeadResponse list."""
    db = get_db()
    query, params = build_leads_query(source, min_score, limit, offset, q, status)
    rows = db.execute(query, params).fetchall()
    return [LeadResponse(**dict(row)) for row in rows]


def get_lead_by_id(lead_id: int) -> LeadResponse | None:
    """Fetch a single lead by ID, or None if not found."""
    db = get_db()
    row = db.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    if row is None:
        return None
    return LeadResponse(**dict(row))


class InvalidStatusError(Exception):
    """Raised when an invalid lead status is provided."""


def update_lead_status(lead_id: int, status: str) -> LeadResponse | None:
    """Update a lead's status. Returns updated lead or None if not found."""
    if status not in VALID_LEAD_STATUSES:
        raise InvalidStatusError(f"Invalid status '{status}'. Must be one of: {', '.join(sorted(VALID_LEAD_STATUSES))}")
    db = get_db()
    row = db.execute("SELECT id FROM leads WHERE id = ?", (lead_id,)).fetchone()
    if row is None:
        return None
    db.execute("UPDATE leads SET status = ? WHERE id = ?", (status, lead_id))
    db.commit()
    updated = db.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    return LeadResponse(**dict(updated))


def get_leads_summary_data(
    source: str | None = None,
    min_score: int | None = None,
    q: str | None = None,
) -> dict:
    """Compute leads summary statistics."""
    db = get_db()
    where, params = build_where_clause(source, min_score, q)

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

    source_rows = db.execute(
        f"SELECT source, COUNT(*) AS cnt FROM leads{where} GROUP BY source ORDER BY cnt DESC",
        params,
    ).fetchall()

    return {
        "total_leads": total_leads,
        "average_score": average_score,
        "low_score_count": bucket_row["low"] or 0,
        "medium_score_count": bucket_row["medium"] or 0,
        "high_score_count": bucket_row["high"] or 0,
        "counts_by_source": {r["source"]: r["cnt"] for r in source_rows},
    }


def query_leads_for_export(
    source: str | None = None,
    min_score: int | None = None,
    limit: int | None = None,
    offset: int | None = None,
    q: str | None = None,
) -> list[dict]:
    """Query leads for CSV export, returning raw dicts."""
    db = get_db()
    query, params = build_leads_query(source, min_score, limit, offset, q)
    rows = db.execute(query, params).fetchall()
    return [dict(row) for row in rows]
