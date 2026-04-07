"""Tests for lead status tracking."""

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


def _create_lead(name="Status Test", email=None, source="test", notes="Tipo: Test"):
    if email is None:
        import uuid
        email = f"status-{uuid.uuid4().hex[:6]}@test.com"
    resp = client.post("/leads", json={"name": name, "email": email, "source": source, "notes": notes})
    return resp.json()["lead"]


# --- Default status ---

def test_new_lead_has_status_new():
    lead = _create_lead()
    assert lead["status"] == "new"


def test_status_in_lead_detail():
    lead = _create_lead()
    resp = client.get(f"/leads/{lead['id']}")
    assert resp.json()["status"] == "new"


# --- Status update ---

def test_update_status_to_contacted():
    lead = _create_lead()
    resp = client.patch(f"/leads/{lead['id']}/status", json={"status": "contacted"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "contacted"


def test_update_status_to_closed():
    lead = _create_lead()
    resp = client.patch(f"/leads/{lead['id']}/status", json={"status": "closed"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "closed"


def test_update_status_to_not_interested():
    lead = _create_lead()
    resp = client.patch(f"/leads/{lead['id']}/status", json={"status": "not_interested"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "not_interested"


def test_update_status_back_to_new():
    lead = _create_lead()
    client.patch(f"/leads/{lead['id']}/status", json={"status": "contacted"})
    resp = client.patch(f"/leads/{lead['id']}/status", json={"status": "new"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "new"


def test_update_status_invalid_rejected():
    lead = _create_lead()
    resp = client.patch(f"/leads/{lead['id']}/status", json={"status": "invalid_status"})
    assert resp.status_code == 422


def test_update_status_empty_rejected():
    lead = _create_lead()
    resp = client.patch(f"/leads/{lead['id']}/status", json={"status": ""})
    assert resp.status_code == 422


def test_update_status_not_found():
    resp = client.patch("/leads/99999/status", json={"status": "contacted"})
    assert resp.status_code == 404


# --- Status in operational surfaces ---

def test_status_in_operational_summary():
    lead = _create_lead(notes="Tipo: Velero")
    client.patch(f"/leads/{lead['id']}/status", json={"status": "contacted"})
    resp = client.get(f"/leads/{lead['id']}/operational")
    assert resp.json()["status"] == "contacted"


def test_status_in_pack():
    lead = _create_lead()
    client.patch(f"/leads/{lead['id']}/status", json={"status": "contacted"})
    resp = client.get(f"/leads/{lead['id']}/pack")
    assert resp.json()["status"] == "contacted"


# --- Operational surface filtering ---

def test_closed_excluded_from_actionable():
    lead = _create_lead(notes="Tipo: Velero")
    client.patch(f"/leads/{lead['id']}/status", json={"status": "closed"})
    resp = client.get("/leads/actionable")
    lead_ids = [item["lead_id"] for item in resp.json()]
    assert lead["id"] not in lead_ids


def test_not_interested_excluded_from_actionable():
    lead = _create_lead(notes="Tipo: Velero")
    client.patch(f"/leads/{lead['id']}/status", json={"status": "not_interested"})
    resp = client.get("/leads/actionable")
    lead_ids = [item["lead_id"] for item in resp.json()]
    assert lead["id"] not in lead_ids


def test_contacted_stays_in_actionable():
    lead = _create_lead(notes="Tipo: Velero")
    client.patch(f"/leads/{lead['id']}/status", json={"status": "contacted"})
    resp = client.get("/leads/actionable")
    lead_ids = [item["lead_id"] for item in resp.json()]
    assert lead["id"] in lead_ids


def test_new_stays_in_actionable():
    lead = _create_lead(notes="Tipo: Velero")
    resp = client.get("/leads/actionable")
    lead_ids = [item["lead_id"] for item in resp.json()]
    assert lead["id"] in lead_ids


def test_closed_excluded_from_queue():
    lead = _create_lead(notes="Tipo: Velero")
    client.patch(f"/leads/{lead['id']}/status", json={"status": "closed"})
    resp = client.get("/internal/queue")
    lead_ids = [item["lead_id"] for item in resp.json()["items"]]
    assert lead["id"] not in lead_ids


def test_closed_excluded_from_worklist():
    lead = _create_lead(notes="Tipo: Velero")
    client.patch(f"/leads/{lead['id']}/status", json={"status": "closed"})
    resp = client.get("/leads/actionable/worklist")
    all_ids = []
    for group in resp.json()["groups"]:
        all_ids.extend(item["lead_id"] for item in group["leads"])
    assert lead["id"] not in all_ids


# --- Full list still shows all statuses ---

def test_leads_list_includes_all_statuses():
    lead = _create_lead()
    client.patch(f"/leads/{lead['id']}/status", json={"status": "closed"})
    resp = client.get("/leads")
    lead_ids = [l["id"] for l in resp.json()]
    assert lead["id"] in lead_ids


# --- Queue ordering: new before contacted ---

def test_queue_new_before_contacted():
    """Within same score, new leads should rank before contacted."""
    lead_new = _create_lead(notes="Tipo: Velero", source="order-test")
    lead_contacted = _create_lead(notes="Tipo: Velero", source="order-test")
    client.patch(f"/leads/{lead_contacted['id']}/status", json={"status": "contacted"})

    resp = client.get("/internal/queue")
    items = resp.json()["items"]
    ids = [item["lead_id"] for item in items]
    if lead_new["id"] in ids and lead_contacted["id"] in ids:
        new_pos = ids.index(lead_new["id"])
        contacted_pos = ids.index(lead_contacted["id"])
        assert new_pos < contacted_pos, f"new at {new_pos} should be before contacted at {contacted_pos}"


# --- Status filter on GET /leads ---

def test_filter_by_status_new():
    lead = _create_lead()
    resp = client.get("/leads", params={"status": "new"})
    assert resp.status_code == 200
    assert all(l["status"] == "new" for l in resp.json())
    assert lead["id"] in [l["id"] for l in resp.json()]


def test_filter_by_status_contacted():
    lead = _create_lead()
    client.patch(f"/leads/{lead['id']}/status", json={"status": "contacted"})
    resp = client.get("/leads", params={"status": "contacted"})
    assert resp.status_code == 200
    assert all(l["status"] == "contacted" for l in resp.json())
    assert lead["id"] in [l["id"] for l in resp.json()]


def test_filter_by_status_closed():
    lead = _create_lead()
    client.patch(f"/leads/{lead['id']}/status", json={"status": "closed"})
    resp = client.get("/leads", params={"status": "closed"})
    assert resp.status_code == 200
    assert lead["id"] in [l["id"] for l in resp.json()]


def test_filter_by_invalid_status():
    resp = client.get("/leads", params={"status": "bogus"})
    assert resp.status_code == 422
