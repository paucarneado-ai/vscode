"""Case and case-scoped entity routes.

All child entities (entities, timeline, evidence, issues, notes, artifacts)
are nested under /cases/{case_id}. Single route file per v2 audit.

Transactional contract:
- Primary INSERT + event INSERT share the same SQLite transaction.
- If emit_event() fails, the transaction is rolled back and 500 is returned.
- If both succeed, db.commit() persists both atomically.
- No write is persisted without its corresponding audit event.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from legal_lab.auth import require_api_key
from legal_lab.db import get_db
from legal_lab.events import emit_event
from legal_lab.schemas import (
    AnalysisArtifactCreate, AnalysisArtifactResponse, AnalysisArtifactUpdate,
    AuditEventResponse, CaseAuditResponse,
    CaseCreate, CaseResponse, CaseCoverageResponse,
    DocumentCreate, DocumentResponse,
    EntityCoverageSection,
    EvidenceChunkCreate, EvidenceChunkResponse,
    EvidenceItemCreate, EvidenceItemResponse,
    LegalIssueCreate, LegalIssueResponse, LegalIssueUpdate,
    PersonEntityCreate, PersonEntityResponse,
    StrategyNoteCreate, StrategyNoteResponse, StrategyNoteUpdate,
    TimelineEventCreate, TimelineEventResponse, TimelineEventUpdate,
    UnlinkedItem,
)

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_api_key)])


def _require_case(case_id: int):
    """Return case row or raise 404."""
    db = get_db()
    row = db.execute("SELECT id FROM cases WHERE id = ?", (case_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    return row


def _commit_with_event(
    db,
    event_type: str,
    entity_type: str,
    entity_id: int,
    origin: str,
    payload: dict,
) -> None:
    """Emit event then commit. Rollback both if event fails."""
    ok = emit_event(event_type, entity_type, entity_id, origin, payload)
    if not ok:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Audit event write failed — transaction rolled back",
        )
    db.commit()


# --- Case CRUD ---

@router.post("/cases", response_model=CaseResponse, status_code=201)
def create_case(body: CaseCreate):
    db = get_db()
    cursor = db.execute(
        "INSERT INTO cases (title, case_type, summary) VALUES (?, ?, ?)",
        (body.title, body.case_type, body.summary),
    )
    case_id = cursor.lastrowid
    _commit_with_event(
        db, "case.created", "case", case_id, "routes.cases",
        {"title": body.title, "case_type": body.case_type},
    )
    row = db.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
    return dict(row)


@router.get("/cases", response_model=list[CaseResponse])
def list_cases():
    db = get_db()
    rows = db.execute("SELECT * FROM cases ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


@router.get("/cases/{case_id}", response_model=CaseResponse)
def get_case(case_id: int):
    db = get_db()
    row = db.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    return dict(row)


# --- PersonEntity ---

@router.post("/cases/{case_id}/entities", response_model=PersonEntityResponse, status_code=201)
def create_entity(case_id: int, body: PersonEntityCreate):
    _require_case(case_id)
    db = get_db()
    cursor = db.execute(
        "INSERT INTO person_entities (case_id, name, role, entity_type, notes) VALUES (?, ?, ?, ?, ?)",
        (case_id, body.name, body.role, body.entity_type, body.notes),
    )
    entity_id = cursor.lastrowid
    _commit_with_event(
        db, "entity.created", "person_entity", entity_id, "routes.cases",
        {"case_id": case_id, "name": body.name, "role": body.role},
    )
    row = db.execute("SELECT * FROM person_entities WHERE id = ?", (entity_id,)).fetchone()
    return dict(row)


@router.get("/cases/{case_id}/entities", response_model=list[PersonEntityResponse])
def list_entities(case_id: int):
    _require_case(case_id)
    db = get_db()
    rows = db.execute(
        "SELECT * FROM person_entities WHERE case_id = ? ORDER BY created_at", (case_id,)
    ).fetchall()
    return [dict(r) for r in rows]


# --- TimelineEvent ---

@router.post("/cases/{case_id}/timeline", response_model=TimelineEventResponse, status_code=201)
def create_timeline_event(case_id: int, body: TimelineEventCreate):
    _require_case(case_id)
    db = get_db()
    cursor = db.execute(
        "INSERT INTO timeline_events (case_id, event_date, event_end_date, description, source_description, confidence) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (case_id, body.event_date, body.event_end_date, body.description, body.source_description, body.confidence),
    )
    event_id = cursor.lastrowid
    _commit_with_event(
        db, "timeline.created", "timeline_event", event_id, "routes.cases",
        {"case_id": case_id, "event_date": body.event_date},
    )
    row = db.execute("SELECT * FROM timeline_events WHERE id = ?", (event_id,)).fetchone()
    return dict(row)


@router.get("/cases/{case_id}/timeline", response_model=list[TimelineEventResponse])
def list_timeline_events(case_id: int):
    _require_case(case_id)
    db = get_db()
    rows = db.execute(
        "SELECT * FROM timeline_events WHERE case_id = ? ORDER BY event_date", (case_id,)
    ).fetchall()
    return [dict(r) for r in rows]


# --- EvidenceItem ---

@router.post("/cases/{case_id}/evidence", response_model=EvidenceItemResponse, status_code=201)
def create_evidence_item(case_id: int, body: EvidenceItemCreate):
    _require_case(case_id)
    db = get_db()
    cursor = db.execute(
        "INSERT INTO evidence_items (case_id, title, evidence_type, location, description) VALUES (?, ?, ?, ?, ?)",
        (case_id, body.title, body.evidence_type, body.location, body.description),
    )
    item_id = cursor.lastrowid
    _commit_with_event(
        db, "evidence.created", "evidence_item", item_id, "routes.cases",
        {"case_id": case_id, "title": body.title},
    )
    row = db.execute("SELECT * FROM evidence_items WHERE id = ?", (item_id,)).fetchone()
    return dict(row)


@router.get("/cases/{case_id}/evidence", response_model=list[EvidenceItemResponse])
def list_evidence_items(case_id: int):
    _require_case(case_id)
    db = get_db()
    rows = db.execute(
        "SELECT * FROM evidence_items WHERE case_id = ? ORDER BY created_at", (case_id,)
    ).fetchall()
    return [dict(r) for r in rows]


# --- LegalIssue ---

@router.post("/cases/{case_id}/issues", response_model=LegalIssueResponse, status_code=201)
def create_legal_issue(case_id: int, body: LegalIssueCreate):
    _require_case(case_id)
    db = get_db()
    cursor = db.execute(
        "INSERT INTO legal_issues (case_id, title, issue_type, analysis) VALUES (?, ?, ?, ?)",
        (case_id, body.title, body.issue_type, body.analysis),
    )
    issue_id = cursor.lastrowid
    _commit_with_event(
        db, "issue.created", "legal_issue", issue_id, "routes.cases",
        {"case_id": case_id, "title": body.title},
    )
    row = db.execute("SELECT * FROM legal_issues WHERE id = ?", (issue_id,)).fetchone()
    return dict(row)


@router.get("/cases/{case_id}/issues", response_model=list[LegalIssueResponse])
def list_legal_issues(case_id: int):
    _require_case(case_id)
    db = get_db()
    rows = db.execute(
        "SELECT * FROM legal_issues WHERE case_id = ? ORDER BY created_at", (case_id,)
    ).fetchall()
    return [dict(r) for r in rows]


# --- StrategyNote ---

@router.post("/cases/{case_id}/notes", response_model=StrategyNoteResponse, status_code=201)
def create_strategy_note(case_id: int, body: StrategyNoteCreate):
    _require_case(case_id)
    db = get_db()
    cursor = db.execute(
        "INSERT INTO strategy_notes (case_id, title, content) VALUES (?, ?, ?)",
        (case_id, body.title, body.content),
    )
    note_id = cursor.lastrowid
    _commit_with_event(
        db, "note.created", "strategy_note", note_id, "routes.cases",
        {"case_id": case_id, "title": body.title},
    )
    row = db.execute("SELECT * FROM strategy_notes WHERE id = ?", (note_id,)).fetchone()
    return dict(row)


@router.get("/cases/{case_id}/notes", response_model=list[StrategyNoteResponse])
def list_strategy_notes(case_id: int):
    _require_case(case_id)
    db = get_db()
    rows = db.execute(
        "SELECT * FROM strategy_notes WHERE case_id = ? ORDER BY created_at", (case_id,)
    ).fetchall()
    return [dict(r) for r in rows]


# --- AnalysisArtifact ---

@router.post("/cases/{case_id}/artifacts", response_model=AnalysisArtifactResponse, status_code=201)
def create_analysis_artifact(case_id: int, body: AnalysisArtifactCreate):
    _require_case(case_id)
    db = get_db()
    cursor = db.execute(
        "INSERT INTO analysis_artifacts (case_id, artifact_type, title, content, status) VALUES (?, ?, ?, ?, ?)",
        (case_id, body.artifact_type, body.title, body.content, body.status),
    )
    artifact_id = cursor.lastrowid
    _commit_with_event(
        db, "artifact.created", "analysis_artifact", artifact_id, "routes.cases",
        {"case_id": case_id, "title": body.title, "artifact_type": body.artifact_type},
    )
    row = db.execute("SELECT * FROM analysis_artifacts WHERE id = ?", (artifact_id,)).fetchone()
    return dict(row)


@router.get("/cases/{case_id}/artifacts", response_model=list[AnalysisArtifactResponse])
def list_analysis_artifacts(case_id: int):
    _require_case(case_id)
    db = get_db()
    rows = db.execute(
        "SELECT * FROM analysis_artifacts WHERE case_id = ? ORDER BY created_at", (case_id,)
    ).fetchall()
    return [dict(r) for r in rows]


# --- Entity updates (PATCH) ---

def _patch_entity(
    case_id: int,
    entity_id: int,
    table: str,
    label: str,
    updates: dict,
    event_type: str,
    entity_type_name: str,
    has_updated_at: bool,
):
    """Apply a partial update to a case-scoped entity. Returns the updated row."""
    _require_case(case_id)
    db = get_db()
    row = db.execute(
        f"SELECT * FROM {table} WHERE id = ? AND case_id = ?", (entity_id, case_id)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"{label} {entity_id} not found in case {case_id}")

    # Filter to only provided (non-None) fields
    fields = {k: v for k, v in updates.items() if v is not None}
    if not fields:
        return dict(row)

    if has_updated_at:
        fields["updated_at"] = datetime.now(timezone.utc).isoformat()

    set_clause = ", ".join(f"{col} = ?" for col in fields)
    values = list(fields.values()) + [entity_id, case_id]
    db.execute(
        f"UPDATE {table} SET {set_clause} WHERE id = ? AND case_id = ?",
        values,
    )
    _commit_with_event(
        db, event_type, entity_type_name, entity_id, "routes.cases",
        {"case_id": case_id, "updated_fields": list(fields.keys())},
    )
    return dict(db.execute(
        f"SELECT * FROM {table} WHERE id = ?", (entity_id,)
    ).fetchone())


@router.patch("/cases/{case_id}/timeline/{event_id}", response_model=TimelineEventResponse)
def update_timeline_event(case_id: int, event_id: int, body: TimelineEventUpdate):
    return _patch_entity(
        case_id, event_id, "timeline_events", "TimelineEvent",
        body.model_dump(), "timeline_event.updated", "timeline_event",
        has_updated_at=False,
    )


@router.patch("/cases/{case_id}/issues/{issue_id}", response_model=LegalIssueResponse)
def update_legal_issue(case_id: int, issue_id: int, body: LegalIssueUpdate):
    return _patch_entity(
        case_id, issue_id, "legal_issues", "LegalIssue",
        body.model_dump(), "legal_issue.updated", "legal_issue",
        has_updated_at=True,
    )


@router.patch("/cases/{case_id}/notes/{note_id}", response_model=StrategyNoteResponse)
def update_strategy_note(case_id: int, note_id: int, body: StrategyNoteUpdate):
    return _patch_entity(
        case_id, note_id, "strategy_notes", "StrategyNote",
        body.model_dump(), "strategy_note.updated", "strategy_note",
        has_updated_at=False,
    )


@router.patch("/cases/{case_id}/artifacts/{artifact_id}", response_model=AnalysisArtifactResponse)
def update_analysis_artifact(case_id: int, artifact_id: int, body: AnalysisArtifactUpdate):
    return _patch_entity(
        case_id, artifact_id, "analysis_artifacts", "AnalysisArtifact",
        body.model_dump(), "analysis_artifact.updated", "analysis_artifact",
        has_updated_at=True,
    )


# --- Document (source-grounding) ---

def _require_document_in_case(case_id: int, document_id: int):
    """Return document row scoped to case, or raise 404."""
    db = get_db()
    row = db.execute(
        "SELECT * FROM documents WHERE id = ? AND case_id = ?", (document_id, case_id)
    ).fetchone()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Document {document_id} not found in case {case_id}",
        )
    return row


@router.post("/cases/{case_id}/documents", response_model=DocumentResponse, status_code=201)
def create_document(case_id: int, body: DocumentCreate):
    _require_case(case_id)
    db = get_db()
    cursor = db.execute(
        "INSERT INTO documents (case_id, document_type, title, source_ref, source_hash, notes) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (case_id, body.document_type, body.title, body.source_ref, body.source_hash, body.notes),
    )
    doc_id = cursor.lastrowid
    _commit_with_event(
        db, "document.created", "document", doc_id, "routes.cases",
        {"case_id": case_id, "title": body.title, "document_type": body.document_type},
    )
    row = db.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    return dict(row)


@router.get("/cases/{case_id}/documents", response_model=list[DocumentResponse])
def list_documents(case_id: int):
    _require_case(case_id)
    db = get_db()
    rows = db.execute(
        "SELECT * FROM documents WHERE case_id = ? ORDER BY created_at", (case_id,)
    ).fetchall()
    return [dict(r) for r in rows]


@router.get("/cases/{case_id}/documents/{document_id}", response_model=DocumentResponse)
def get_document(case_id: int, document_id: int):
    row = _require_document_in_case(case_id, document_id)
    return dict(row)


# --- EvidenceChunk (source-grounding) ---

@router.post("/cases/{case_id}/chunks", response_model=EvidenceChunkResponse, status_code=201)
def create_evidence_chunk(case_id: int, body: EvidenceChunkCreate):
    _require_case(case_id)
    doc_row = _require_document_in_case(case_id, body.document_id)
    db = get_db()
    cursor = db.execute(
        "INSERT INTO evidence_chunks (case_id, document_id, text, page_from, page_to, location_label, timestamp_ref) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (case_id, body.document_id, body.text, body.page_from, body.page_to,
         body.location_label, body.timestamp_ref),
    )
    chunk_id = cursor.lastrowid
    _commit_with_event(
        db, "chunk.created", "evidence_chunk", chunk_id, "routes.cases",
        {"case_id": case_id, "document_id": body.document_id},
    )
    row = db.execute("SELECT * FROM evidence_chunks WHERE id = ?", (chunk_id,)).fetchone()
    return dict(row)


@router.get("/cases/{case_id}/chunks", response_model=list[EvidenceChunkResponse])
def list_chunks_for_case(case_id: int):
    _require_case(case_id)
    db = get_db()
    rows = db.execute(
        "SELECT * FROM evidence_chunks WHERE case_id = ? ORDER BY created_at", (case_id,)
    ).fetchall()
    return [dict(r) for r in rows]


@router.get(
    "/cases/{case_id}/documents/{document_id}/chunks",
    response_model=list[EvidenceChunkResponse],
)
def list_chunks_for_document(case_id: int, document_id: int):
    _require_document_in_case(case_id, document_id)
    db = get_db()
    rows = db.execute(
        "SELECT * FROM evidence_chunks WHERE case_id = ? AND document_id = ? ORDER BY created_at",
        (case_id, document_id),
    ).fetchall()
    return [dict(r) for r in rows]


@router.get("/cases/{case_id}/chunks/{chunk_id}", response_model=EvidenceChunkResponse)
def get_chunk(case_id: int, chunk_id: int):
    _require_case(case_id)
    db = get_db()
    row = db.execute(
        "SELECT * FROM evidence_chunks WHERE id = ? AND case_id = ?", (chunk_id, case_id)
    ).fetchone()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Chunk {chunk_id} not found in case {case_id}",
        )
    return dict(row)


# --- Case coverage / source-grounding summary ---

def _entity_coverage(
    db, case_id: int, entity_table: str, link_table: str,
    entity_id_col: str, label_col: str,
) -> EntityCoverageSection:
    """Compute linked/unlinked counts for one entity type in a case."""
    all_rows = db.execute(
        f"SELECT id, {label_col} AS label FROM {entity_table} WHERE case_id = ?",
        (case_id,),
    ).fetchall()
    total = len(all_rows)

    if total == 0:
        return EntityCoverageSection(total=0, linked=0, unlinked=0, unlinked_items=[])

    linked_ids = {
        row[0] for row in db.execute(
            f"SELECT DISTINCT {entity_id_col} FROM {link_table} WHERE case_id = ?",
            (case_id,),
        ).fetchall()
    }
    linked = len(linked_ids)
    unlinked_items = [
        UnlinkedItem(id=row["id"], label=row["label"])
        for row in all_rows if row["id"] not in linked_ids
    ]
    return EntityCoverageSection(
        total=total, linked=linked, unlinked=total - linked,
        unlinked_items=unlinked_items,
    )


@router.get("/cases/{case_id}/coverage", response_model=CaseCoverageResponse)
def get_case_coverage(case_id: int):
    db = get_db()
    case_row = db.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
    if case_row is None:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    docs_count = db.execute(
        "SELECT COUNT(*) AS cnt FROM documents WHERE case_id = ?", (case_id,)
    ).fetchone()["cnt"]
    chunks_count = db.execute(
        "SELECT COUNT(*) AS cnt FROM evidence_chunks WHERE case_id = ?", (case_id,)
    ).fetchone()["cnt"]

    return CaseCoverageResponse(
        case_id=case_id,
        title=case_row["title"],
        documents_count=docs_count,
        evidence_chunks_count=chunks_count,
        timeline_events=_entity_coverage(
            db, case_id, "timeline_events", "timeline_event_chunk_links",
            "timeline_event_id", "description",
        ),
        legal_issues=_entity_coverage(
            db, case_id, "legal_issues", "legal_issue_chunk_links",
            "legal_issue_id", "title",
        ),
        strategy_notes=_entity_coverage(
            db, case_id, "strategy_notes", "strategy_note_chunk_links",
            "strategy_note_id", "title",
        ),
        analysis_artifacts=_entity_coverage(
            db, case_id, "analysis_artifacts", "analysis_artifact_chunk_links",
            "artifact_id", "title",
        ),
    )


# --- Case audit ---

@router.get("/cases/{case_id}/audit", response_model=CaseAuditResponse)
def get_case_audit(case_id: int):
    """Return all audit events relevant to a case.

    Scoping strategy:
    - Case creation events: entity_type='case' AND entity_id=case_id
    - Child/link events: json_extract(payload, '$.case_id') = case_id

    This depends on the convention that all child-entity and link event
    payloads include a "case_id" field. Events that omit case_id from
    their payload will not appear here.
    """
    db = get_db()
    case_row = db.execute("SELECT id FROM cases WHERE id = ?", (case_id,)).fetchone()
    if case_row is None:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    rows = db.execute(
        """
        SELECT * FROM events
        WHERE (entity_type = 'case' AND entity_id = ?)
           OR json_extract(payload, '$.case_id') = ?
        ORDER BY created_at, id
        """,
        (case_id, case_id),
    ).fetchall()

    events = [dict(r) for r in rows]
    return CaseAuditResponse(
        case_id=case_id,
        total_events=len(events),
        events=events,
    )
