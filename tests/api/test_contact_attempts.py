"""Tests for the Contact Attempts MVP block.

Covers: POST/GET endpoints, auth, enum validation, enrichment of
followup surfaces, and non-regression of existing followup behavior.
"""

import re
import tempfile

import apps.api.db as db_module

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
db_module.DATABASE_PATH = _tmp.name
db_module.reset_db()
db_module.init_db()

from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)

_SQLITE_DT_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")


def _create_lead(name, email, source, notes="test lead"):
    """Create a lead, return lead_id."""
    resp = client.post("/leads", json={
        "name": name, "email": email, "source": source, "notes": notes,
    })
    if resp.status_code == 409:
        leads = client.get("/leads", params={"q": email}).json()
        return leads[0]["id"]
    return resp.json()["lead"]["id"]


def _create_lead_with_outcome(name, email, source, outcome, reason=None):
    """Create a lead and record an outcome. Returns lead_id."""
    lid = _create_lead(name, email, source)
    payload = {"lead_id": lid, "outcome": outcome}
    if reason:
        payload["reason"] = reason
    client.post("/internal/outcomes", json=payload)
    return lid


def _post_attempt(lead_id, **overrides):
    """Post a contact attempt with sensible defaults. Returns response."""
    body = {
        "lead_id": lead_id,
        "channel": "email",
        "attempt_type": "first_contact",
        "status": "sent",
        **overrides,
    }
    return client.post("/internal/contact-attempts", json=body)


# ---------------------------------------------------------------------------
# POST tests
# ---------------------------------------------------------------------------


def test_post_happy_path():
    lid = _create_lead("CA Test 1", "ca1@test.com", "test")
    resp = _post_attempt(lid)
    assert resp.status_code == 201
    data = resp.json()
    assert isinstance(data["id"], int)
    assert data["lead_id"] == lid
    assert data["channel"] == "email"
    assert data["direction"] == "outbound"
    assert data["attempt_type"] == "first_contact"
    assert data["status"] == "sent"
    assert data["provider"] == "manual"
    assert data["note"] is None
    assert data["external_ref"] is None
    assert _SQLITE_DT_RE.match(data["created_at"])


def test_post_with_defaults():
    lid = _create_lead("CA Defaults", "ca-def@test.com", "test")
    resp = client.post("/internal/contact-attempts", json={
        "lead_id": lid,
        "channel": "phone",
        "attempt_type": "follow_up",
        "status": "answered",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["direction"] == "outbound"
    assert data["provider"] == "manual"


def test_post_with_note_and_external_ref():
    lid = _create_lead("CA Note", "ca-note@test.com", "test")
    resp = _post_attempt(lid, note="Called, voicemail", external_ref="n8n-job-42")
    assert resp.status_code == 201
    data = resp.json()
    assert data["note"] == "Called, voicemail"
    assert data["external_ref"] == "n8n-job-42"


def test_post_lead_not_found():
    resp = _post_attempt(999999)
    assert resp.status_code == 404


def test_post_invalid_channel():
    lid = _create_lead("CA Chan", "ca-chan@test.com", "test")
    resp = _post_attempt(lid, channel="sms")
    assert resp.status_code == 422


def test_post_invalid_status():
    lid = _create_lead("CA Stat", "ca-stat@test.com", "test")
    resp = _post_attempt(lid, status="completed")
    assert resp.status_code == 422


def test_post_invalid_attempt_type():
    lid = _create_lead("CA Type", "ca-type@test.com", "test")
    resp = _post_attempt(lid, attempt_type="final_attempt")
    assert resp.status_code == 422


def test_post_invalid_provider():
    lid = _create_lead("CA Prov", "ca-prov@test.com", "test")
    resp = _post_attempt(lid, provider="zapier")
    assert resp.status_code == 422


def test_post_append_only():
    lid = _create_lead("CA Append", "ca-append@test.com", "test")
    r1 = _post_attempt(lid, status="sent")
    r2 = _post_attempt(lid, status="no_answer")
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] != r2.json()["id"]
    # GET should show both
    get_resp = client.get(f"/internal/contact-attempts/{lid}")
    assert get_resp.json()["attempt_count"] == 2


def test_post_event_emitted():
    lid = _create_lead("CA Event", "ca-event@test.com", "test")
    _post_attempt(lid, channel="whatsapp", status="failed", provider="n8n")
    events = client.get("/internal/events", params={"event_type": "contact_attempt.recorded"}).json()
    matching = [e for e in events["items"] if e["entity_id"] == lid]
    assert len(matching) >= 1
    payload = matching[-1]["payload"]
    assert payload["channel"] == "whatsapp"
    assert payload["status"] == "failed"
    assert payload["provider"] == "n8n"


# ---------------------------------------------------------------------------
# GET tests
# ---------------------------------------------------------------------------


def test_get_shape():
    lid = _create_lead("CA GetShape", "ca-getshape@test.com", "test")
    _post_attempt(lid)
    resp = client.get(f"/internal/contact-attempts/{lid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["lead_id"] == lid
    assert isinstance(data["attempt_count"], int)
    assert isinstance(data["recent_attempts"], list)
    assert "last_contacted_at" in data
    assert "last_attempt_status" in data
    assert "last_channel" in data


def test_get_lead_not_found():
    resp = client.get("/internal/contact-attempts/999999")
    assert resp.status_code == 404


def test_get_empty():
    lid = _create_lead("CA Empty", "ca-empty@test.com", "test")
    resp = client.get(f"/internal/contact-attempts/{lid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["attempt_count"] == 0
    assert data["recent_attempts"] == []
    assert data["last_contacted_at"] is None
    assert data["last_attempt_status"] is None
    assert data["last_channel"] is None


def test_get_ordering():
    """Most recent attempt first, with id DESC tiebreaker."""
    lid = _create_lead("CA Order", "ca-order@test.com", "test")
    _post_attempt(lid, status="sent")
    _post_attempt(lid, status="no_answer")
    _post_attempt(lid, status="answered")
    resp = client.get(f"/internal/contact-attempts/{lid}")
    items = resp.json()["recent_attempts"]
    assert len(items) == 3
    # IDs should be descending (most recent insert last = highest id)
    ids = [i["id"] for i in items]
    assert ids == sorted(ids, reverse=True)


def test_get_multiple():
    lid = _create_lead("CA Multi", "ca-multi@test.com", "test")
    _post_attempt(lid, channel="email")
    _post_attempt(lid, channel="phone")
    _post_attempt(lid, channel="whatsapp")
    resp = client.get(f"/internal/contact-attempts/{lid}")
    data = resp.json()
    assert data["attempt_count"] == 3
    assert len(data["recent_attempts"]) == 3


def test_get_last_fields_reflect_most_recent():
    lid = _create_lead("CA Last", "ca-last@test.com", "test")
    _post_attempt(lid, channel="email", status="sent")
    _post_attempt(lid, channel="phone", status="answered")
    resp = client.get(f"/internal/contact-attempts/{lid}")
    data = resp.json()
    assert data["last_channel"] == "phone"
    assert data["last_attempt_status"] == "answered"
    assert data["last_contacted_at"] is not None


# ---------------------------------------------------------------------------
# Enrichment tests
# ---------------------------------------------------------------------------


def _ensure_enrichment_leads():
    """Create test leads for enrichment tests at runtime (not import time).

    Returns (enriched_lead_id, no_attempt_lead_id).
    Idempotent — uses unique emails to avoid 409 on repeated calls.
    """
    enrich_lid = _create_lead_with_outcome(
        "Enrich Lead RT", "enrich-rt@test.com", "test", "no_answer",
    )
    _post_attempt(enrich_lid, channel="email", status="sent")
    no_attempt_lid = _create_lead_with_outcome(
        "No Attempt RT", "noattempt-rt@test.com", "test", "no_answer",
    )
    return enrich_lid, no_attempt_lid


def test_followup_queue_enrichment_present():
    enrich_lid, _ = _ensure_enrichment_leads()
    resp = client.get("/internal/followup-queue")
    data = resp.json()
    item = next(i for i in data["items"] if i["lead_id"] == enrich_lid)
    assert "last_contacted_at" in item
    assert "contact_attempts_count" in item
    assert "recently_contacted" in item
    assert item["contact_attempts_count"] >= 1


def test_followup_queue_recently_contacted_true():
    enrich_lid, _ = _ensure_enrichment_leads()
    resp = client.get("/internal/followup-queue")
    data = resp.json()
    item = next(i for i in data["items"] if i["lead_id"] == enrich_lid)
    assert item["recently_contacted"] is True
    assert item["last_contacted_at"] is not None


def test_followup_queue_no_attempts_defaults():
    _, no_attempt_lid = _ensure_enrichment_leads()
    resp = client.get("/internal/followup-queue")
    data = resp.json()
    item = next(i for i in data["items"] if i["lead_id"] == no_attempt_lid)
    assert item["last_contacted_at"] is None
    assert item["contact_attempts_count"] == 0
    assert item["recently_contacted"] is False


def test_followup_handoffs_enrichment():
    enrich_lid, _ = _ensure_enrichment_leads()
    resp = client.get("/internal/followup-handoffs")
    data = resp.json()
    item = next(i for i in data["items"] if i["lead_id"] == enrich_lid)
    assert item["contact_attempts_count"] >= 1
    assert item["recently_contacted"] is True


def test_followup_automation_enrichment_in_payload():
    enrich_lid, _ = _ensure_enrichment_leads()
    resp = client.get("/internal/followup-automation")
    data = resp.json()
    item = next(i for i in data["items"] if i["lead_id"] == enrich_lid)
    payload = item["payload"]
    assert "last_contacted_at" in payload
    assert "contact_attempts_count" in payload
    assert "recently_contacted" in payload
    assert payload["contact_attempts_count"] >= 1


def test_daily_actions_followup_enrichment():
    resp = client.get("/internal/daily-actions")
    data = resp.json()
    followup_items = data["top_followup"]
    if not followup_items:
        return  # no followup items in daily actions cap
    # Check that enrichment fields are present on at least one item
    item = followup_items[0]
    assert "last_contacted_at" in item
    assert "contact_attempts_count" in item
    assert "recently_contacted" in item


# ---------------------------------------------------------------------------
# Non-regression tests
# ---------------------------------------------------------------------------


def test_existing_followup_surfaces_still_work():
    """All 4 followup endpoints return 200 with expected top-level shape."""
    for endpoint in [
        "/internal/followup-queue",
        "/internal/followup-handoffs",
        "/internal/followup-automation",
        "/internal/daily-actions",
    ]:
        resp = client.get(endpoint)
        assert resp.status_code == 200, f"{endpoint} returned {resp.status_code}"


def test_followup_queue_ordering_unchanged():
    """Score DESC, lead_id ASC ordering is preserved."""
    resp = client.get("/internal/followup-queue")
    items = resp.json()["items"]
    if len(items) < 2:
        return
    for a, b in zip(items, items[1:]):
        assert (a["score"], -a["lead_id"]) >= (b["score"], -b["lead_id"])
