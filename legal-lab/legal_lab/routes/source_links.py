"""Source-anchored cross-reference routes.

Links analytical entities (timeline events, legal issues, strategy notes,
analysis artifacts) to evidence chunks. All links are case-scoped with
composite FK integrity at the DB level.

Transactional contract: same as cases.py — primary INSERT + event in same
transaction, rollback on event failure.
"""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from legal_lab.auth import require_api_key
from legal_lab.db import get_db
from legal_lab.events import emit_event
from legal_lab.schemas import ChunkLinkCreate, LinkedChunkResponse

router = APIRouter(
    prefix="/cases/{case_id}",
    dependencies=[Depends(require_api_key)],
)


def _require_case(case_id: int):
    db = get_db()
    row = db.execute("SELECT id FROM cases WHERE id = ?", (case_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")


def _require_entity_in_case(table: str, entity_id: int, case_id: int, label: str):
    db = get_db()
    row = db.execute(
        f"SELECT id FROM {table} WHERE id = ? AND case_id = ?", (entity_id, case_id)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"{label} {entity_id} not found in case {case_id}")


def _require_chunk_in_case(chunk_id: int, case_id: int):
    db = get_db()
    row = db.execute(
        "SELECT id FROM evidence_chunks WHERE id = ? AND case_id = ?", (chunk_id, case_id)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Chunk {chunk_id} not found in case {case_id}")


def _commit_with_event(db, event_type, entity_type, entity_id, origin, payload):
    ok = emit_event(event_type, entity_type, entity_id, origin, payload)
    if not ok:
        db.rollback()
        raise HTTPException(status_code=500, detail="Audit event write failed — transaction rolled back")
    db.commit()


_LINKED_CHUNK_SQL = """
    SELECT
        l.id AS link_id,
        ec.id AS chunk_id,
        ec.document_id,
        d.title AS document_title,
        ec.text,
        ec.page_from,
        ec.page_to,
        ec.location_label,
        ec.timestamp_ref,
        d.source_ref,
        l.relation_type,
        l.created_at AS linked_at
    FROM {link_table} l
    JOIN evidence_chunks ec ON ec.id = l.chunk_id AND ec.case_id = l.case_id
    JOIN documents d ON d.id = ec.document_id AND d.case_id = ec.case_id
    WHERE l.{entity_col} = ? AND l.case_id = ?
    ORDER BY ec.created_at
"""


def _create_link(
    case_id: int,
    entity_table: str,
    entity_id: int,
    entity_label: str,
    entity_col: str,
    link_table: str,
    event_type: str,
    body: ChunkLinkCreate,
):
    _require_case(case_id)
    _require_entity_in_case(entity_table, entity_id, case_id, entity_label)
    _require_chunk_in_case(body.chunk_id, case_id)

    db = get_db()
    try:
        cursor = db.execute(
            f"INSERT INTO {link_table} (case_id, {entity_col}, chunk_id, relation_type) "
            "VALUES (?, ?, ?, ?)",
            (case_id, entity_id, body.chunk_id, body.relation_type),
        )
    except sqlite3.IntegrityError as exc:
        db.rollback()
        if "UNIQUE" in str(exc).upper():
            raise HTTPException(status_code=409, detail="This link already exists")
        raise

    link_id = cursor.lastrowid
    _commit_with_event(
        db, event_type, link_table, link_id, "routes.source_links",
        {"case_id": case_id, entity_col: entity_id, "chunk_id": body.chunk_id},
    )
    return {"id": link_id, "status": "linked"}


def _list_linked_chunks(case_id: int, entity_table: str, entity_id: int,
                         entity_label: str, entity_col: str, link_table: str):
    _require_case(case_id)
    _require_entity_in_case(entity_table, entity_id, case_id, entity_label)

    db = get_db()
    sql = _LINKED_CHUNK_SQL.format(link_table=link_table, entity_col=entity_col)
    rows = db.execute(sql, (entity_id, case_id)).fetchall()
    return [dict(r) for r in rows]


# --- TimelineEvent links ---

@router.post("/timeline/{event_id}/links", status_code=201)
def link_chunk_to_timeline_event(case_id: int, event_id: int, body: ChunkLinkCreate):
    return _create_link(
        case_id, "timeline_events", event_id, "TimelineEvent", "timeline_event_id",
        "timeline_event_chunk_links", "link.timeline_event_chunk.created", body,
    )


@router.get("/timeline/{event_id}/links", response_model=list[LinkedChunkResponse])
def list_timeline_event_links(case_id: int, event_id: int):
    return _list_linked_chunks(
        case_id, "timeline_events", event_id, "TimelineEvent", "timeline_event_id",
        "timeline_event_chunk_links",
    )


# --- LegalIssue links ---

@router.post("/issues/{issue_id}/links", status_code=201)
def link_chunk_to_legal_issue(case_id: int, issue_id: int, body: ChunkLinkCreate):
    return _create_link(
        case_id, "legal_issues", issue_id, "LegalIssue", "legal_issue_id",
        "legal_issue_chunk_links", "link.legal_issue_chunk.created", body,
    )


@router.get("/issues/{issue_id}/links", response_model=list[LinkedChunkResponse])
def list_legal_issue_links(case_id: int, issue_id: int):
    return _list_linked_chunks(
        case_id, "legal_issues", issue_id, "LegalIssue", "legal_issue_id",
        "legal_issue_chunk_links",
    )


# --- StrategyNote links ---

@router.post("/notes/{note_id}/links", status_code=201)
def link_chunk_to_strategy_note(case_id: int, note_id: int, body: ChunkLinkCreate):
    return _create_link(
        case_id, "strategy_notes", note_id, "StrategyNote", "strategy_note_id",
        "strategy_note_chunk_links", "link.strategy_note_chunk.created", body,
    )


@router.get("/notes/{note_id}/links", response_model=list[LinkedChunkResponse])
def list_strategy_note_links(case_id: int, note_id: int):
    return _list_linked_chunks(
        case_id, "strategy_notes", note_id, "StrategyNote", "strategy_note_id",
        "strategy_note_chunk_links",
    )


# --- AnalysisArtifact links ---

@router.post("/artifacts/{artifact_id}/links", status_code=201)
def link_chunk_to_artifact(case_id: int, artifact_id: int, body: ChunkLinkCreate):
    return _create_link(
        case_id, "analysis_artifacts", artifact_id, "AnalysisArtifact", "artifact_id",
        "analysis_artifact_chunk_links", "link.analysis_artifact_chunk.created", body,
    )


@router.get("/artifacts/{artifact_id}/links", response_model=list[LinkedChunkResponse])
def list_artifact_links(case_id: int, artifact_id: int):
    return _list_linked_chunks(
        case_id, "analysis_artifacts", artifact_id, "AnalysisArtifact", "artifact_id",
        "analysis_artifact_chunk_links",
    )
