"""Minimal internal event spine.

Append-only event log for operational traceability.
Best-effort: emit failures never break the primary operation.
"""

import json
from datetime import datetime, timezone

from apps.api.db import get_db


def emit_event(
    event_type: str,
    entity_type: str,
    entity_id: int,
    origin_module: str,
    payload: dict | None = None,
) -> None:
    """Append one event to the events table. Best-effort — failures are silent."""
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
        db.commit()
    except Exception:
        pass
