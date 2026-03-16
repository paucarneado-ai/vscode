"""Lightweight event emitter — logs events and optionally persists to DB."""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def emit_event(
    event_type: str,
    entity_type: str,
    entity_id: str,
    source: str,
    payload: dict,
) -> None:
    """Fire-and-forget event emission. Never raises."""
    try:
        logger.info(
            "event=%s entity=%s:%s source=%s",
            event_type,
            entity_type,
            entity_id,
            source,
        )
    except Exception:
        pass
