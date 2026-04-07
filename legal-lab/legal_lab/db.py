"""SQLite persistence for legal-lab.

Uses a single-connection singleton per process. This is intentional:
- All route handlers share one connection and therefore one implicit transaction.
- emit_event() and the primary INSERT share the same transaction because they
  use the same connection. db.commit() commits both atomically.
- This guarantee holds ONLY because get_db() returns a singleton. If the
  application moves to connection pooling, multiple workers, or a different
  database engine, the transactional coupling between primary writes and
  event writes must be re-evaluated.
"""

import os
import sqlite3

DATABASE_PATH = os.getenv("DATABASE_PATH", "legal_lab.db")

_connection: sqlite3.Connection | None = None


def get_db() -> sqlite3.Connection:
    """Return the singleton DB connection. Creates it on first call.

    The connection has row_factory=sqlite3.Row and foreign_keys=ON.
    All callers share this connection and its transaction state.
    """
    global _connection
    if _connection is None:
        _connection = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        _connection.row_factory = sqlite3.Row
        _connection.execute("PRAGMA foreign_keys = ON")
    return _connection


def init_db() -> None:
    db = get_db()

    db.execute("""
        CREATE TABLE IF NOT EXISTS cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            case_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            summary TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS person_entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER NOT NULL REFERENCES cases(id),
            name TEXT NOT NULL,
            role TEXT NOT NULL,
            entity_type TEXT NOT NULL DEFAULT 'person',
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_person_entities_case ON person_entities(case_id)"
    )

    db.execute("""
        CREATE TABLE IF NOT EXISTS timeline_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER NOT NULL REFERENCES cases(id),
            event_date TEXT NOT NULL,
            event_end_date TEXT,
            description TEXT NOT NULL,
            source_description TEXT,
            confidence TEXT NOT NULL DEFAULT 'unknown',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (id, case_id)
        )
    """)
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_timeline_events_case ON timeline_events(case_id)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_timeline_events_date ON timeline_events(event_date)"
    )

    db.execute("""
        CREATE TABLE IF NOT EXISTS evidence_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER NOT NULL REFERENCES cases(id),
            title TEXT NOT NULL,
            evidence_type TEXT NOT NULL,
            location TEXT,
            description TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_evidence_items_case ON evidence_items(case_id)"
    )

    db.execute("""
        CREATE TABLE IF NOT EXISTS legal_issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER NOT NULL REFERENCES cases(id),
            title TEXT NOT NULL,
            issue_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            analysis TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (id, case_id)
        )
    """)
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_legal_issues_case ON legal_issues(case_id)"
    )

    db.execute("""
        CREATE TABLE IF NOT EXISTS strategy_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER NOT NULL REFERENCES cases(id),
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (id, case_id)
        )
    """)
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_strategy_notes_case ON strategy_notes(case_id)"
    )

    db.execute("""
        CREATE TABLE IF NOT EXISTS analysis_artifacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER NOT NULL REFERENCES cases(id),
            artifact_type TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (id, case_id)
        )
    """)
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_analysis_artifacts_case ON analysis_artifacts(case_id)"
    )

    db.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER NOT NULL REFERENCES cases(id),
            document_type TEXT NOT NULL,
            title TEXT NOT NULL,
            source_ref TEXT,
            source_hash TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            imported_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (id, case_id)
        )
    """)
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_documents_case ON documents(case_id)"
    )

    db.execute("""
        CREATE TABLE IF NOT EXISTS evidence_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER NOT NULL REFERENCES cases(id),
            document_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            page_from INTEGER,
            page_to INTEGER,
            location_label TEXT,
            timestamp_ref TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (id, case_id),
            FOREIGN KEY (document_id, case_id) REFERENCES documents(id, case_id)
        )
    """)
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_evidence_chunks_case ON evidence_chunks(case_id)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_evidence_chunks_document ON evidence_chunks(document_id)"
    )

    # --- Source-anchored cross-reference link tables ---

    db.execute("""
        CREATE TABLE IF NOT EXISTS timeline_event_chunk_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER NOT NULL,
            timeline_event_id INTEGER NOT NULL,
            chunk_id INTEGER NOT NULL,
            relation_type TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (timeline_event_id, chunk_id),
            FOREIGN KEY (timeline_event_id, case_id) REFERENCES timeline_events(id, case_id),
            FOREIGN KEY (chunk_id, case_id) REFERENCES evidence_chunks(id, case_id)
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS legal_issue_chunk_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER NOT NULL,
            legal_issue_id INTEGER NOT NULL,
            chunk_id INTEGER NOT NULL,
            relation_type TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (legal_issue_id, chunk_id),
            FOREIGN KEY (legal_issue_id, case_id) REFERENCES legal_issues(id, case_id),
            FOREIGN KEY (chunk_id, case_id) REFERENCES evidence_chunks(id, case_id)
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS strategy_note_chunk_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER NOT NULL,
            strategy_note_id INTEGER NOT NULL,
            chunk_id INTEGER NOT NULL,
            relation_type TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (strategy_note_id, chunk_id),
            FOREIGN KEY (strategy_note_id, case_id) REFERENCES strategy_notes(id, case_id),
            FOREIGN KEY (chunk_id, case_id) REFERENCES evidence_chunks(id, case_id)
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS analysis_artifact_chunk_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER NOT NULL,
            artifact_id INTEGER NOT NULL,
            chunk_id INTEGER NOT NULL,
            relation_type TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (artifact_id, chunk_id),
            FOREIGN KEY (artifact_id, case_id) REFERENCES analysis_artifacts(id, case_id),
            FOREIGN KEY (chunk_id, case_id) REFERENCES evidence_chunks(id, case_id)
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id INTEGER NOT NULL,
            origin_module TEXT NOT NULL,
            payload TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_events_event_type ON events(event_type)"
    )

    db.commit()

    _verify_schema(db)


def _verify_schema(db: sqlite3.Connection) -> None:
    """Verify that critical schema constraints are present in the live database.

    This catches the case where an existing database was created before a
    hardening change. CREATE TABLE IF NOT EXISTS skips the DDL if the table
    already exists, so constraint changes are silently ignored. This check
    detects that and fails loudly.
    """
    # The evidence_chunks table must have a composite FK referencing
    # documents(id, case_id) — not just a simple FK to documents(id).
    # We inspect the actual foreign_key_list pragma output.
    fks = db.execute("PRAGMA foreign_key_list(evidence_chunks)").fetchall()
    has_composite_doc_fk = False
    for fk in fks:
        # pragma columns: id, seq, table, from, to
        if fk["table"] == "documents" and fk["from"] == "case_id" and fk["to"] == "case_id":
            has_composite_doc_fk = True
            break

    if not has_composite_doc_fk:
        raise RuntimeError(
            "SCHEMA INCOMPATIBLE: evidence_chunks table is missing the composite "
            "foreign key (document_id, case_id) REFERENCES documents(id, case_id). "
            "This database was likely created before the source-grounding integrity "
            "hardening. To fix: delete the existing legal_lab.db and restart, or "
            "manually recreate the documents and evidence_chunks tables with the "
            "updated DDL from db.py."
        )

    # Verify parent tables have UNIQUE (id, case_id) required as composite FK targets.
    # Without this, link table INSERTs fail at runtime with "foreign key mismatch"
    # even though the link table DDL was accepted.
    _composite_unique_required = [
        "timeline_events",
        "legal_issues",
        "strategy_notes",
        "analysis_artifacts",
        "evidence_chunks",
    ]
    for table in _composite_unique_required:
        if not _has_composite_unique(db, table, {"id", "case_id"}):
            raise RuntimeError(
                f"SCHEMA INCOMPATIBLE: {table} is missing UNIQUE(id, case_id). "
                f"This is required as a composite FK target for source-link tables. "
                f"This database was likely created before the cross-reference block. "
                f"Delete legal_lab.db and restart."
            )

    # Verify link tables have composite FKs to both parent entity and evidence_chunks.
    _link_checks = [
        ("timeline_event_chunk_links", "evidence_chunks"),
        ("legal_issue_chunk_links", "evidence_chunks"),
        ("strategy_note_chunk_links", "evidence_chunks"),
        ("analysis_artifact_chunk_links", "evidence_chunks"),
    ]
    for link_table, expected_ref in _link_checks:
        fks = db.execute(f"PRAGMA foreign_key_list({link_table})").fetchall()
        has_chunk_case_fk = any(
            fk["table"] == expected_ref and fk["from"] == "case_id" and fk["to"] == "case_id"
            for fk in fks
        )
        if not has_chunk_case_fk:
            raise RuntimeError(
                f"SCHEMA INCOMPATIBLE: {link_table} is missing composite FK to "
                f"{expected_ref}(id, case_id). Delete legal_lab.db and restart."
            )


def _has_composite_unique(db: sqlite3.Connection, table: str, columns: set[str]) -> bool:
    """Check if a table has a UNIQUE constraint covering exactly the given columns."""
    indices = db.execute(f"PRAGMA index_list({table})").fetchall()
    for idx in indices:
        if idx["unique"] != 1:
            continue
        idx_cols = db.execute(f"PRAGMA index_info({idx['name']})").fetchall()
        idx_col_names = {col["name"] for col in idx_cols}
        if idx_col_names == columns:
            return True
    return False


def reset_db() -> None:
    """Close and discard the current connection. Used by tests."""
    global _connection
    if _connection is not None:
        _connection.close()
    _connection = None
