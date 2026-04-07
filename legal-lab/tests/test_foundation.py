"""Foundation tests: schema, health, events, auth, FK enforcement."""

import sqlite3
import tempfile
import logging

from fastapi.testclient import TestClient

from legal_lab import db as db_module
from legal_lab.config import settings

# Isolated temp DB for this test module
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
db_module.DATABASE_PATH = _tmp.name
db_module.reset_db()
db_module.init_db()

from legal_lab.app import app  # noqa: E402 — must import after DB override

client = TestClient(app, raise_server_exceptions=False)

EXPECTED_TABLES = [
    "cases", "person_entities", "timeline_events", "evidence_items",
    "legal_issues", "strategy_notes", "analysis_artifacts",
    "documents", "evidence_chunks",
    "timeline_event_chunk_links", "legal_issue_chunk_links",
    "strategy_note_chunk_links", "analysis_artifact_chunk_links",
    "events",
]


class TestSchemaInit:
    def test_all_tables_exist(self):
        db = db_module.get_db()
        rows = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        table_names = {r["name"] for r in rows}
        for expected in EXPECTED_TABLES:
            assert expected in table_names, f"Missing table: {expected}"

    def test_idempotent_init(self):
        """Calling init_db() twice does not raise."""
        db_module.init_db()
        db = db_module.get_db()
        row = db.execute("SELECT COUNT(*) AS cnt FROM cases").fetchone()
        assert row["cnt"] >= 0


class TestForeignKeys:
    def test_pragma_foreign_keys_is_on(self):
        db = db_module.get_db()
        row = db.execute("PRAGMA foreign_keys").fetchone()
        assert row[0] == 1, "PRAGMA foreign_keys must be ON"

    def test_db_rejects_orphan_child_insert(self):
        """Direct SQL INSERT with a nonexistent case_id must raise IntegrityError."""
        db = db_module.get_db()
        try:
            db.execute(
                "INSERT INTO person_entities (case_id, name, role, entity_type) VALUES (?, ?, ?, ?)",
                (999999, "Ghost", "phantom", "person"),
            )
            db.rollback()
            assert False, "Expected IntegrityError for FK violation"
        except sqlite3.IntegrityError:
            db.rollback()

    def test_db_rejects_chunk_with_mismatched_case_and_document(self):
        """DB must reject an evidence_chunk whose case_id differs from its document's case_id.

        This is the composite FK constraint: evidence_chunks(document_id, case_id)
        REFERENCES documents(id, case_id). Even if both case and document exist
        independently, the pair must match.
        """
        db = db_module.get_db()

        # Create two cases
        db.execute("INSERT INTO cases (title, case_type) VALUES ('Case A', 'test')")
        case_a = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.execute("INSERT INTO cases (title, case_type) VALUES ('Case B', 'test')")
        case_b = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Create a document in case A
        db.execute(
            "INSERT INTO documents (case_id, document_type, title) VALUES (?, 'report', 'Doc in A')",
            (case_a,),
        )
        doc_in_a = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.commit()

        # Try to insert a chunk referencing doc_in_a but with case_b — must fail
        try:
            db.execute(
                "INSERT INTO evidence_chunks (case_id, document_id, text) VALUES (?, ?, 'mismatch')",
                (case_b, doc_in_a),
            )
            db.rollback()
            assert False, "Expected IntegrityError for composite FK violation (case/document mismatch)"
        except sqlite3.IntegrityError:
            db.rollback()

        # Verify the valid same-case insert still works
        db.execute(
            "INSERT INTO evidence_chunks (case_id, document_id, text) VALUES (?, ?, 'valid')",
            (case_a, doc_in_a),
        )
        db.commit()
        row = db.execute(
            "SELECT * FROM evidence_chunks WHERE case_id = ? AND document_id = ?",
            (case_a, doc_in_a),
        ).fetchone()
        assert row is not None
        assert row["text"] == "valid"

    def test_db_rejects_cross_case_chunk_link(self):
        """Link table composite FK prevents linking a chunk from a different case."""
        db = db_module.get_db()

        # Create two cases
        db.execute("INSERT INTO cases (title, case_type) VALUES ('Link Case A', 'test')")
        case_a = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.execute("INSERT INTO cases (title, case_type) VALUES ('Link Case B', 'test')")
        case_b = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Create timeline event in case A
        db.execute(
            "INSERT INTO timeline_events (case_id, event_date, description) VALUES (?, '2024-01-01', 'event')",
            (case_a,),
        )
        event_in_a = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Create document + chunk in case B
        db.execute(
            "INSERT INTO documents (case_id, document_type, title) VALUES (?, 'report', 'Doc B')",
            (case_b,),
        )
        doc_in_b = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.execute(
            "INSERT INTO evidence_chunks (case_id, document_id, text) VALUES (?, ?, 'chunk in B')",
            (case_b, doc_in_b),
        )
        chunk_in_b = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.commit()

        # Try to link event_in_a (case A) to chunk_in_b (case B) — must fail
        try:
            db.execute(
                "INSERT INTO timeline_event_chunk_links (case_id, timeline_event_id, chunk_id) "
                "VALUES (?, ?, ?)",
                (case_a, event_in_a, chunk_in_b),
            )
            db.rollback()
            assert False, "Expected IntegrityError for cross-case link"
        except sqlite3.IntegrityError:
            db.rollback()


class TestSchemaVerification:
    def test_verify_schema_passes_on_correct_db(self):
        """Current DB was created with correct DDL — verification must pass."""
        from legal_lab.db import _verify_schema
        db = db_module.get_db()
        # Should not raise
        _verify_schema(db)

    def test_verify_schema_rejects_pre_hardening_db(self):
        """A DB with old-style simple FK on evidence_chunks must be rejected."""
        import tempfile
        pre_hardening_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        old_conn = sqlite3.connect(pre_hardening_tmp.name)
        old_conn.row_factory = sqlite3.Row
        old_conn.execute("PRAGMA foreign_keys = ON")

        # Create tables with the OLD DDL (no composite FK, no UNIQUE on documents)
        old_conn.execute("""
            CREATE TABLE cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                case_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                summary TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        old_conn.execute("""
            CREATE TABLE documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL REFERENCES cases(id),
                document_type TEXT NOT NULL,
                title TEXT NOT NULL,
                source_ref TEXT,
                source_hash TEXT,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                imported_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        old_conn.execute("""
            CREATE TABLE evidence_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL REFERENCES cases(id),
                document_id INTEGER NOT NULL REFERENCES documents(id),
                text TEXT NOT NULL,
                page_from INTEGER,
                page_to INTEGER,
                location_label TEXT,
                timestamp_ref TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        old_conn.commit()

        from legal_lab.db import _verify_schema
        try:
            _verify_schema(old_conn)
            assert False, "Expected RuntimeError for missing composite FK"
        except RuntimeError as exc:
            assert "SCHEMA INCOMPATIBLE" in str(exc)
            assert "composite foreign key" in str(exc)
        finally:
            old_conn.close()

    def test_verify_schema_rejects_parent_tables_missing_composite_unique(self):
        """A DB where parent tables lack UNIQUE(id, case_id) must be rejected.

        Without UNIQUE(id, case_id) on parent tables, composite FKs in link
        tables cause 'foreign key mismatch' OperationalError at INSERT time,
        even though the link table DDL was accepted.
        """
        import tempfile
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        conn = sqlite3.connect(tmp.name)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")

        # Old parent tables WITHOUT UNIQUE(id, case_id)
        conn.execute("""
            CREATE TABLE cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL, case_type TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL REFERENCES cases(id),
                document_type TEXT NOT NULL, title TEXT NOT NULL,
                source_ref TEXT, source_hash TEXT, notes TEXT,
                created_at TEXT, imported_at TEXT,
                UNIQUE (id, case_id)
            )
        """)
        conn.execute("""
            CREATE TABLE evidence_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL REFERENCES cases(id),
                document_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                page_from INTEGER, page_to INTEGER,
                location_label TEXT, timestamp_ref TEXT, created_at TEXT,
                FOREIGN KEY (document_id, case_id) REFERENCES documents(id, case_id)
            )
        """)
        # Old timeline_events — NO UNIQUE(id, case_id)
        conn.execute("""
            CREATE TABLE timeline_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL REFERENCES cases(id),
                event_date TEXT NOT NULL, description TEXT NOT NULL,
                source_description TEXT,
                confidence TEXT NOT NULL DEFAULT 'unknown',
                created_at TEXT
            )
        """)
        # Similarly old for the others
        conn.execute("""
            CREATE TABLE legal_issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL REFERENCES cases(id),
                title TEXT NOT NULL, issue_type TEXT NOT NULL,
                status TEXT, analysis TEXT, created_at TEXT, updated_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE strategy_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL REFERENCES cases(id),
                title TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE analysis_artifacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL REFERENCES cases(id),
                artifact_type TEXT NOT NULL, title TEXT NOT NULL,
                content TEXT NOT NULL, status TEXT, created_at TEXT, updated_at TEXT
            )
        """)
        conn.commit()

        from legal_lab.db import _verify_schema
        try:
            _verify_schema(conn)
            assert False, "Expected RuntimeError for missing UNIQUE(id, case_id) on parent tables"
        except RuntimeError as exc:
            assert "SCHEMA INCOMPATIBLE" in str(exc)
            assert "UNIQUE(id, case_id)" in str(exc)
        finally:
            conn.close()


class TestHealth:
    def test_health_basic(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["app"] == "LegalLab"

    def test_health_detail_returns_table_counts(self):
        resp = client.get("/health/detail")
        assert resp.status_code == 200
        data = resp.json()
        assert "checks" in data
        checks = data["checks"]
        assert checks["db"] == "ok"
        for table in EXPECTED_TABLES:
            assert f"{table}_count" in checks

    def test_health_detail_status_ok_when_healthy(self):
        resp = client.get("/health/detail")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_health_detail_status_degraded_on_db_failure(self):
        """If DB check fails, top-level status must reflect degradation."""
        original_path = db_module.DATABASE_PATH
        db_module.reset_db()
        db_module.DATABASE_PATH = "/nonexistent/path/broken.db"
        db_module.reset_db()

        resp = client.get("/health/detail")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"
        assert "error" in data["checks"]["db"]

        # Restore
        db_module.DATABASE_PATH = original_path
        db_module.reset_db()
        db_module.init_db()

    def test_health_no_auth_required(self):
        """Health endpoints are public even when auth is configured."""
        original_key = settings.api_key
        try:
            object.__setattr__(settings, "api_key", "secret-test-key")
            resp = client.get("/health")
            assert resp.status_code == 200
        finally:
            object.__setattr__(settings, "api_key", original_key)


class TestEventMechanism:
    def test_emit_event_returns_true_on_success(self):
        from legal_lab.events import emit_event
        result = emit_event("test.event", "test", 1, "test_foundation", {"key": "value"})
        assert result is True
        db_module.get_db().commit()

        db = db_module.get_db()
        row = db.execute(
            "SELECT * FROM events WHERE event_type = 'test.event'"
        ).fetchone()
        assert row is not None
        assert row["entity_type"] == "test"
        assert row["entity_id"] == 1

    def test_emit_event_returns_false_on_failure(self, caplog):
        """Event failures are reported, not silent."""
        from legal_lab.events import emit_event

        original_path = db_module.DATABASE_PATH
        db_module.reset_db()
        db_module.DATABASE_PATH = "/nonexistent/path/impossible.db"
        db_module.reset_db()

        with caplog.at_level(logging.ERROR):
            result = emit_event("fail.event", "test", 1, "test_foundation")

        assert result is False
        assert "Failed to emit event" in caplog.text

        # Restore
        db_module.DATABASE_PATH = original_path
        db_module.reset_db()
        db_module.init_db()

    def test_emit_does_not_commit(self):
        """Event insert is part of caller's transaction, not auto-committed."""
        from legal_lab.events import emit_event

        db = db_module.get_db()
        count_before = db.execute("SELECT COUNT(*) AS cnt FROM events").fetchone()["cnt"]

        emit_event("nocommit.test", "test", 999, "test_foundation")
        db.execute("ROLLBACK")

        count_after = db.execute("SELECT COUNT(*) AS cnt FROM events").fetchone()["cnt"]
        assert count_after == count_before

    def test_event_failure_rolls_back_primary_write(self):
        """Route-level: if event emission fails, primary write is also rolled back."""
        db = db_module.get_db()
        count_before = db.execute("SELECT COUNT(*) AS cnt FROM cases").fetchone()["cnt"]

        # Sabotage: drop events table to make emit_event fail
        db.execute("DROP TABLE events")
        db.commit()

        resp = client.post("/cases", json={
            "title": "Should Not Persist",
            "case_type": "test",
        })
        assert resp.status_code == 500
        assert "Audit event write failed" in resp.json()["detail"]

        # Restore events table
        db_module.reset_db()
        db_module.init_db()
        db = db_module.get_db()

        count_after = db.execute("SELECT COUNT(*) AS cnt FROM cases").fetchone()["cnt"]
        assert count_after == count_before, "Primary write must be rolled back when event fails"


class TestAuth:
    def _set_auth(self, api_key: str, app_env: str):
        object.__setattr__(settings, "api_key", api_key)
        object.__setattr__(settings, "app_env", app_env)

    def _restore_auth(self, original_key, original_env):
        object.__setattr__(settings, "api_key", original_key)
        object.__setattr__(settings, "app_env", original_env)

    def test_fail_closed_production_no_key(self):
        """Production with no key configured => 503 on protected endpoints."""
        orig_key, orig_env = settings.api_key, settings.app_env
        try:
            self._set_auth("", "production")
            resp = client.get("/cases")
            assert resp.status_code == 503
        finally:
            self._restore_auth(orig_key, orig_env)

    def test_missing_key_returns_401(self):
        """Auth enabled, no header sent => 401."""
        orig_key, orig_env = settings.api_key, settings.app_env
        try:
            self._set_auth("real-secret", "production")
            resp = client.get("/cases")  # no header
            assert resp.status_code == 401
        finally:
            self._restore_auth(orig_key, orig_env)

    def test_invalid_key_returns_403(self):
        """Auth enabled, wrong key => 403."""
        orig_key, orig_env = settings.api_key, settings.app_env
        try:
            self._set_auth("real-secret", "production")
            resp = client.get("/cases", headers={"X-API-Key": "wrong-secret"})
            assert resp.status_code == 403
        finally:
            self._restore_auth(orig_key, orig_env)

    def test_valid_key_returns_200(self):
        """Auth enabled, correct key => allowed."""
        orig_key, orig_env = settings.api_key, settings.app_env
        try:
            self._set_auth("real-secret", "production")
            resp = client.get("/cases", headers={"X-API-Key": "real-secret"})
            assert resp.status_code == 200
        finally:
            self._restore_auth(orig_key, orig_env)

    def test_dev_bypass_when_no_key(self):
        """Development with no key => auth bypassed, requests allowed."""
        orig_key, orig_env = settings.api_key, settings.app_env
        try:
            self._set_auth("", "development")
            resp = client.get("/cases")  # no header
            assert resp.status_code == 200
        finally:
            self._restore_auth(orig_key, orig_env)
