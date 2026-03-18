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
    # Add status column to existing databases that don't have it
    try:
        db.execute("SELECT status FROM leads LIMIT 1")
    except Exception:
        db.execute("ALTER TABLE leads ADD COLUMN status TEXT NOT NULL DEFAULT 'new'")
    db.commit()


def reset_db() -> None:
    """Close and discard the current connection. Used by tests."""
    global _connection
    if _connection is not None:
        _connection.close()
    _connection = None
