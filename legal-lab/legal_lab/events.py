"""Event spine for legal-lab.

Adapted from the OpenClaw pattern with stricter failure semantics:
- Failures are logged and reported, never silently swallowed.
- Returns a boolean indicating success/failure so callers can decide.
- Does NOT call db.commit() internally. The caller controls the transaction.

Guarantees (under the current single-connection SQLite model):
- If emit_event returns True, the INSERT was executed on the singleton connection.
  It shares the caller's transaction and will persist only when the caller commits.
- If emit_event returns False, the INSERT failed. The exception is logged.
  The caller should rollback to discard any preceding uncommitted writes.
- Because get_db() returns a singleton, the primary write and the event write
  are always in the same transaction. db.commit() persists both atomically.

Does NOT guarantee:
- Durability independent of the caller's commit.
- Atomicity if the application moves to connection pooling or multi-worker
  deployment. The singleton-based coupling would break.
"""

import json
import logging
from datetime import datetime, timezone

from legal_lab.db import get_db

logger = logging.getLogger(__name__)


def emit_event(
    event_type: str,
    entity_type: str,
    entity_id: int,
    origin_module: str,
    payload: dict | None = None,
) -> bool:
    """Append one event to the events table.

    Returns True on success, False on failure. Failures are logged.
    Does not commit — caller controls the transaction boundary.
    """
    try:
        db = get_db()
        db.execute(
            "INSERT INTO events (event_type, entity_type, entity_id, origin_module, payload, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                event_type,
                entity_type,
                entity_id,
                origin_module,
                json.dumps(payload or {}, ensure_ascii=False, separators=(",", ":")),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        return True
    except Exception:
        logger.exception(
            "Failed to emit event: type=%s entity=%s/%s module=%s",
            event_type, entity_type, entity_id, origin_module,
        )
        return False
