import os
import sqlite3

DATABASE_PATH = os.getenv("DATABASE_PATH", "openclaw.db")

_connection: sqlite3.Connection | None = None


def get_db() -> sqlite3.Connection:
    global _connection
    if _connection is None:
        _connection = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        _connection.row_factory = sqlite3.Row
    return _connection


def init_db() -> None:
    db = get_db()
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            source TEXT NOT NULL,
            notes TEXT,
            score INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'new',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_leads_email_source ON leads (email, source)"
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS dispatch_claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL UNIQUE,
            claimed_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id INTEGER NOT NULL,
            origin_module TEXT NOT NULL,
            payload TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_events_event_type ON events (event_type)"
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS lead_outcomes (
            lead_id INTEGER PRIMARY KEY REFERENCES leads(id),
            outcome TEXT NOT NULL,
            reason TEXT,
            notes TEXT,
            recorded_at TEXT NOT NULL
        )
        """
    )
    # Add status column to existing databases that don't have it
    try:
        db.execute("SELECT status FROM leads LIMIT 1")
    except Exception:
        db.execute("ALTER TABLE leads ADD COLUMN status TEXT NOT NULL DEFAULT 'new'")

    # --- Commercial Intelligence schema additions ---

    # Add loss_reason and recorded_by to lead_outcomes (idempotent ALTERs)
    for col, typedef in [
        ("loss_reason", "TEXT"),
        ("recorded_by", "TEXT NOT NULL DEFAULT 'system'"),
    ]:
        try:
            db.execute(f"SELECT {col} FROM lead_outcomes LIMIT 1")
        except Exception:
            db.execute(f"ALTER TABLE lead_outcomes ADD COLUMN {col} {typedef}")

    # Outcome history — append-only log of every outcome change
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS lead_outcome_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL REFERENCES leads(id),
            outcome TEXT NOT NULL,
            loss_reason TEXT,
            reason TEXT,
            notes TEXT,
            recorded_by TEXT NOT NULL DEFAULT 'system',
            recorded_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_loh_lead ON lead_outcome_history(lead_id)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_loh_date ON lead_outcome_history(recorded_at)"
    )

    # --- Contact Attempts ---
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS contact_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL REFERENCES leads(id),
            channel TEXT NOT NULL,
            direction TEXT NOT NULL,
            attempt_type TEXT NOT NULL,
            status TEXT NOT NULL,
            provider TEXT NOT NULL DEFAULT 'manual',
            note TEXT,
            external_ref TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_contact_attempts_lead_date "
        "ON contact_attempts (lead_id, created_at DESC)"
    )

    # Backfill: create one synthetic initial row per existing lead_outcome
    # that has no history yet. recorded_by = 'backfill'.
    # Does NOT reconstruct real prior history — only preserves the current snapshot.
    db.execute(
        """
        INSERT INTO lead_outcome_history (lead_id, outcome, loss_reason, reason, notes, recorded_by, recorded_at)
        SELECT lo.lead_id, lo.outcome, lo.loss_reason, lo.reason, lo.notes, 'backfill', lo.recorded_at
        FROM lead_outcomes lo
        WHERE NOT EXISTS (
            SELECT 1 FROM lead_outcome_history loh WHERE loh.lead_id = lo.lead_id
        )
        """
    )

    db.commit()


def reset_db() -> None:
    """Close and discard the current connection. Used by tests."""
    global _connection
    if _connection is not None:
        _connection.close()
    _connection = None
