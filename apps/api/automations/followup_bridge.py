"""Minimal follow-up automation bridge.

Consumes GET /internal/followup-automation and maps items into
execution-ready outputs. Read-only consumer — does not send, schedule,
or mutate any lead state.

This is a colocated consumer bridge for MVP pragmatism, not core API
business logic. It trusts API ordering and business rules as delivered.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class BridgeItem:
    lead_id: int
    to: str
    subject: str
    body: str
    channel: str
    priority: int
    source: str
    score: int
    rating: str


@dataclass
class BridgeResult:
    fetched_at: str
    total_fetched: int
    total_mapped: int
    items: list[BridgeItem]
    errors: list[str] = field(default_factory=list)


_SUBJECT_BY_RATING: dict[str, str] = {
    "high": "Following up \u2014 let\u2019s connect this week",
    "medium": "Quick follow-up",
    "low": "Checking in",
}


def _map_item(item: dict) -> BridgeItem:
    """Map a single automation item into a BridgeItem.

    Raises KeyError or TypeError on missing/invalid fields.
    """
    payload = item["payload"]
    rating = payload["rating"]
    return BridgeItem(
        lead_id=item["lead_id"],
        to=payload["email"],
        subject=_SUBJECT_BY_RATING.get(rating, "Follow-up"),
        body=payload["suggested_message"],
        channel=item["channel"],
        priority=item["priority"],
        source=payload["source"],
        score=payload["score"],
        rating=rating,
    )


def run_followup_bridge(client) -> BridgeResult:
    """Consume /internal/followup-automation and map items into execution-ready outputs.

    Args:
        client: any object with a ``.get(path)`` method returning
                a response with ``.status_code`` and ``.json()``.
    """
    now = datetime.now(timezone.utc).isoformat()

    resp = client.get("/internal/followup-automation")
    if resp.status_code != 200:
        return BridgeResult(
            fetched_at=now,
            total_fetched=0,
            total_mapped=0,
            items=[],
            errors=[f"fetch failed: HTTP {resp.status_code}"],
        )

    data = resp.json()
    if (
        not isinstance(data, dict)
        or not isinstance(data.get("items"), list)
        or not isinstance(data.get("total"), int)
        or not isinstance(data.get("generated_at"), str)
    ):
        return BridgeResult(
            fetched_at=now,
            total_fetched=0,
            total_mapped=0,
            items=[],
            errors=["invalid response shape: requires dict with 'generated_at' (str), 'total' (int), 'items' (list)"],
        )

    raw_items = data["items"]
    # total_fetched reflects the API-declared total exactly, not len(items).
    # These may differ if the API applies limits or if items are malformed.
    total_fetched = data["total"]
    mapped: list[BridgeItem] = []
    errors: list[str] = []

    for idx, item in enumerate(raw_items):
        try:
            mapped.append(_map_item(item))
        except (KeyError, TypeError) as exc:
            lead_id = item.get("lead_id", "unknown") if isinstance(item, dict) else "unknown"
            errors.append(f"item {idx} (lead_id={lead_id}): {exc}")

    return BridgeResult(
        fetched_at=now,
        total_fetched=total_fetched,
        total_mapped=len(mapped),
        items=mapped,
        errors=errors,
    )
