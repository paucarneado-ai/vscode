"""Tests for the follow-up automation bridge."""

import tempfile

import apps.api.db as db_module

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
db_module.DATABASE_PATH = _tmp.name
db_module.reset_db()
db_module.init_db()

from fastapi.testclient import TestClient

from apps.api.automations.followup_bridge import BridgeItem, BridgeResult, run_followup_bridge
from apps.api.main import app

client = TestClient(app)


def _create_lead_with_outcome(name, email, source, outcome):
    """Create a lead and record an outcome. Returns lead_id."""
    resp = client.post("/leads", json={
        "name": name, "email": email, "source": source,
    })
    if resp.status_code == 409:
        leads = client.get("/leads", params={"q": email}).json()
        lid = leads[0]["id"]
    else:
        lid = resp.json()["lead"]["id"]
    client.post("/internal/outcomes", json={
        "lead_id": lid, "outcome": outcome,
    })
    return lid


# Seed some no_answer leads for tests
_lead_ids = []
for i in range(3):
    _lead_ids.append(_create_lead_with_outcome(
        f"Bridge Test {i}", f"bridge{i}@t.com", "bridge_src", "no_answer",
    ))


def test_bridge_shape():
    result = run_followup_bridge(client)
    assert isinstance(result, BridgeResult)
    assert isinstance(result.fetched_at, str)
    assert isinstance(result.total_fetched, int)
    assert isinstance(result.total_mapped, int)
    assert isinstance(result.items, list)
    assert isinstance(result.errors, list)
    assert result.total_fetched >= 3
    assert result.total_mapped >= 3
    assert len(result.errors) == 0


def test_bridge_maps_items():
    result = run_followup_bridge(client)
    assert len(result.items) >= 1
    item = result.items[0]
    assert isinstance(item, BridgeItem)
    assert isinstance(item.lead_id, int)
    assert isinstance(item.to, str)
    assert "@" in item.to
    assert isinstance(item.subject, str)
    assert len(item.subject) > 0
    assert isinstance(item.body, str)
    assert len(item.body) > 0
    assert isinstance(item.channel, str)
    assert isinstance(item.priority, int)
    assert isinstance(item.source, str)
    assert isinstance(item.score, int)
    assert isinstance(item.rating, str)


def test_bridge_subject_by_rating():
    """Subject must be deterministic based on rating."""
    result = run_followup_bridge(client)
    for item in result.items:
        if item.rating == "high":
            assert item.subject == "Following up \u2014 let\u2019s connect this week"
        elif item.rating == "medium":
            assert item.subject == "Quick follow-up"
        elif item.rating == "low":
            assert item.subject == "Checking in"
        else:
            # Unknown rating should get fallback
            assert item.subject == "Follow-up"


def test_bridge_subject_fallback_for_unknown_rating():
    """Bridge must use 'Follow-up' fallback for unrecognized rating values."""

    class FakeResponse:
        def __init__(self, status_code, data):
            self.status_code = status_code
            self._data = data

        def json(self):
            return self._data

    class FakeClient:
        def get(self, path):
            return FakeResponse(200, {
                "generated_at": "2026-01-01T00:00:00+00:00",
                "total": 1,
                "items": [{
                    "lead_id": 999,
                    "channel": "email",
                    "action": "retry_contact",
                    "priority": 0,
                    "payload": {
                        "name": "Test",
                        "email": "test@example.com",
                        "source": "web",
                        "score": 42,
                        "rating": "ultra_rare",
                        "instruction": "Retry contact",
                        "suggested_message": "Hi Test",
                    },
                }],
            })

    result = run_followup_bridge(FakeClient())
    assert result.total_mapped == 1
    assert result.items[0].subject == "Follow-up"
    assert result.items[0].rating == "ultra_rare"
    assert result.errors == []


def test_bridge_empty_when_no_leads():
    """Bridge must handle empty automation response gracefully."""

    class FakeClient:
        def get(self, path):
            return FakeResponse(200, {
                "generated_at": "2026-01-01T00:00:00+00:00",
                "total": 0,
                "items": [],
            })

    class FakeResponse:
        def __init__(self, status_code, data):
            self.status_code = status_code
            self._data = data

        def json(self):
            return self._data

    result = run_followup_bridge(FakeClient())
    assert result.total_fetched == 0
    assert result.total_mapped == 0
    assert result.items == []
    assert result.errors == []


def test_bridge_preserves_priority_order():
    """Bridge must not reorder items from the API."""
    result = run_followup_bridge(client)
    priorities = [item.priority for item in result.items]
    assert priorities == sorted(priorities)


def test_bridge_errors_on_bad_response():
    """Non-200 response must produce a global error."""

    class FakeClient:
        def get(self, path):
            return FakeResponse(500)

    class FakeResponse:
        def __init__(self, status_code):
            self.status_code = status_code

        def json(self):
            return {}

    result = run_followup_bridge(FakeClient())
    assert result.total_fetched == 0
    assert result.total_mapped == 0
    assert result.items == []
    assert len(result.errors) == 1
    assert "HTTP 500" in result.errors[0]


def test_bridge_fields_include_source_score_rating():
    """Each mapped item must have explicit source, score, and rating fields."""
    result = run_followup_bridge(client)
    for item in result.items:
        assert hasattr(item, "source")
        assert hasattr(item, "score")
        assert hasattr(item, "rating")
        assert item.rating in ("low", "medium", "high")
        assert isinstance(item.score, int)
        assert isinstance(item.source, str)


def test_bridge_skips_invalid_item_and_records_error():
    """Invalid individual items must be skipped with error recorded."""

    class FakeClient:
        def get(self, path):
            return FakeResponse(200, {
                "generated_at": "2026-01-01T00:00:00+00:00",
                "total": 2,
                "items": [
                    {
                        "lead_id": 1,
                        "channel": "email",
                        "action": "retry_contact",
                        "priority": 0,
                        "payload": {
                            "name": "Valid",
                            "email": "valid@t.com",
                            "source": "web",
                            "score": 60,
                            "rating": "medium",
                            "instruction": "Retry",
                            "suggested_message": "Hi Valid",
                        },
                    },
                    {
                        "lead_id": 2,
                        "channel": "email",
                        # missing payload entirely
                    },
                ],
            })

    class FakeResponse:
        def __init__(self, status_code, data):
            self.status_code = status_code
            self._data = data

        def json(self):
            return self._data

    result = run_followup_bridge(FakeClient())
    assert result.total_fetched == 2
    assert result.total_mapped == 1
    assert len(result.items) == 1
    assert result.items[0].lead_id == 1
    assert len(result.errors) == 1
    assert "lead_id=2" in result.errors[0]


def test_bridge_does_not_reorder_items_from_api():
    """Two consecutive bridge runs must return items in the same order as the API."""
    auto_resp = client.get("/internal/followup-automation").json()
    api_ids = [item["lead_id"] for item in auto_resp["items"]]

    result = run_followup_bridge(client)
    bridge_ids = [item.lead_id for item in result.items]

    assert bridge_ids == api_ids


class _FakeResponse:
    """Minimal fake response for shape-validation tests."""
    def __init__(self, status_code, data=None):
        self.status_code = status_code
        self._data = data

    def json(self):
        return self._data


def test_bridge_errors_on_invalid_top_level_shape():
    """Global failure when top-level response is missing required fields or has wrong types."""
    bad_shapes = [
        # not a dict
        [1, 2, 3],
        # missing generated_at
        {"total": 0, "items": []},
        # missing items
        {"generated_at": "2026-01-01T00:00:00+00:00", "total": 0},
        # missing total
        {"generated_at": "2026-01-01T00:00:00+00:00", "items": []},
        # total wrong type
        {"generated_at": "2026-01-01T00:00:00+00:00", "total": "zero", "items": []},
        # items wrong type
        {"generated_at": "2026-01-01T00:00:00+00:00", "total": 0, "items": "not a list"},
        # generated_at wrong type
        {"generated_at": 12345, "total": 0, "items": []},
    ]
    for shape in bad_shapes:
        class FakeClient:
            _shape = shape
            def get(self, path):
                return _FakeResponse(200, self._shape)

        result = run_followup_bridge(FakeClient())
        assert result.total_fetched == 0, f"Expected global failure for shape: {shape}"
        assert result.total_mapped == 0
        assert result.items == []
        assert len(result.errors) == 1
        assert "invalid response shape" in result.errors[0]


def test_bridge_total_fetched_reflects_api_declared_total():
    """total_fetched must be the API-declared total, not len(items)."""

    class FakeClient:
        def get(self, path):
            return _FakeResponse(200, {
                "generated_at": "2026-01-01T00:00:00+00:00",
                "total": 5,  # API says 5
                "items": [    # but only 2 items delivered
                    {
                        "lead_id": 1, "channel": "email",
                        "action": "retry_contact", "priority": 0,
                        "payload": {
                            "name": "A", "email": "a@t.com", "source": "web",
                            "score": 60, "rating": "medium",
                            "instruction": "Retry", "suggested_message": "Hi A",
                        },
                    },
                    {
                        "lead_id": 2, "channel": "email",
                        "action": "retry_contact", "priority": 1,
                        "payload": {
                            "name": "B", "email": "b@t.com", "source": "web",
                            "score": 40, "rating": "low",
                            "instruction": "Retry", "suggested_message": "Hi B",
                        },
                    },
                ],
            })

    result = run_followup_bridge(FakeClient())
    assert result.total_fetched == 5  # API-declared, not len(items)
    assert result.total_mapped == 2   # actually mapped


def test_bridge_works_with_enriched_payload():
    """Bridge must still work after followup-automation payload is enriched
    with contact attempt fields (last_contacted_at, contact_attempts_count,
    recently_contacted). These new fields must be silently ignored."""
    # Create a no_answer lead and record a contact attempt against it
    lid = _create_lead_with_outcome(
        "Bridge Enrich", "bridge-enrich@t.com", "bridge_src", "no_answer",
    )
    client.post("/internal/contact-attempts", json={
        "lead_id": lid,
        "channel": "email",
        "attempt_type": "first_contact",
        "status": "sent",
    })

    result = run_followup_bridge(client)
    assert result.total_fetched >= 1
    assert result.total_mapped >= 1
    assert len(result.errors) == 0

    # Verify the enriched lead is among the mapped items
    mapped_ids = [item.lead_id for item in result.items]
    assert lid in mapped_ids
