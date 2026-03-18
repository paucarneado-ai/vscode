"""Operational lead composition service.

Extracted from routes/leads.py to reduce router fan-out.
Composes LeadOperationalSummary from DB rows + scoring + actions + leadpack.
"""

from datetime import datetime, timezone

from apps.api.db import get_db
from apps.api.schemas import LeadOperationalSummary, LeadPackResponse
from apps.api.services.actions import build_priority_reason, determine_next_action, get_instruction, should_alert
from apps.api.services.leadpack import build_summary, get_rating


def _extract_phone(notes: str | None) -> str | None:
    """Extract phone number from structured notes if present."""
    if not notes:
        return None
    for line in notes.split("\n"):
        stripped = line.strip()
        lower = stripped.lower()
        if lower.startswith("teléfono:") or lower.startswith("telefono:"):
            value = stripped.split(":", 1)[1].strip()
            return value if value else None
    return None


def build_operational_summary(lead: dict) -> LeadOperationalSummary:
    """Compose a LeadOperationalSummary from a raw DB row dict."""
    rating = get_rating(lead["score"])
    next_action = determine_next_action(lead["score"], lead["notes"])
    return LeadOperationalSummary(
        lead_id=lead["id"],
        name=lead["name"],
        email=lead["email"],
        source=lead["source"],
        score=lead["score"],
        status=lead.get("status", "new"),
        rating=rating,
        next_action=next_action,
        instruction=get_instruction(next_action),
        priority_reason=build_priority_reason(lead["score"], lead["notes"], lead["source"]),
        alert=should_alert(lead["score"]),
        summary=build_summary(lead["name"], lead["source"], lead["score"], rating),
        phone=_extract_phone(lead["notes"]),
        created_at=lead["created_at"],
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


def get_actionable_leads(
    source: str | None = None,
    limit: int | None = None,
    include_closed: bool = False,
) -> list[LeadOperationalSummary]:
    """Return actionable leads as LeadOperationalSummary list.

    Actionable = score >= 40 OR has notes.
    By default excludes leads with status 'closed' or 'not_interested'.
    """
    db = get_db()
    conditions: list[str] = [
        "(score >= 40 OR (notes IS NOT NULL AND TRIM(notes) != ''))"
    ]
    if not include_closed:
        conditions.append("(status IS NULL OR status NOT IN ('closed', 'not_interested'))")
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
    return [build_operational_summary(dict(row)) for row in rows]


def build_lead_pack(lead: dict) -> LeadPackResponse:
    """Compose a LeadPackResponse from a raw DB row dict."""
    rating = get_rating(lead["score"])
    next_action = determine_next_action(lead["score"], lead["notes"])
    return LeadPackResponse(
        lead_id=lead["id"],
        created_at=lead["created_at"],
        name=lead["name"],
        email=lead["email"],
        source=lead["source"],
        notes=lead["notes"],
        score=lead["score"],
        status=lead.get("status", "new"),
        rating=rating,
        summary=build_summary(lead["name"], lead["source"], lead["score"], rating),
        next_action=next_action,
        alert=should_alert(lead["score"]),
    )


def get_lead_pack_by_id(lead_id: int) -> LeadPackResponse | None:
    """Fetch a lead by ID and return its pack, or None if not found."""
    db = get_db()
    row = db.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    if row is None:
        return None
    return build_lead_pack(dict(row))


def get_lead_operational_by_id(lead_id: int) -> LeadOperationalSummary | None:
    """Fetch a lead by ID and return its operational summary, or None if not found."""
    pack = get_lead_pack_by_id(lead_id)
    if pack is None:
        return None
    return LeadOperationalSummary(
        lead_id=pack.lead_id,
        name=pack.name,
        email=pack.email,
        source=pack.source,
        score=pack.score,
        status=pack.status,
        rating=pack.rating,
        next_action=pack.next_action,
        instruction=get_instruction(pack.next_action),
        priority_reason=build_priority_reason(pack.score, pack.notes, pack.source),
        alert=pack.alert,
        summary=pack.summary,
        phone=_extract_phone(pack.notes),
        created_at=pack.created_at,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
