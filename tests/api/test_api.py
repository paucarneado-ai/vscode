import tempfile

import apps.api.db as db_module

# Use a temporary SQLite file for tests
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
db_module.DATABASE_PATH = _tmp.name
db_module.reset_db()
db_module.init_db()

from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)

VALID_LEAD = {
    "name": "Test User",
    "email": "test@example.com",
    "source": "test",
    "notes": "interested in demo",
}


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_create_lead_valid():
    response = client.post("/leads", json=VALID_LEAD)
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "lead received"
    lead = data["lead"]
    assert lead["name"] == "Test User"
    assert lead["email"] == "test@example.com"
    assert lead["score"] == 70  # base 50 + source "test" 10 + notes 10
    assert "id" in lead
    assert "created_at" in lead


def test_create_lead_invalid():
    payload = {"name": ""}  # missing email, empty name
    response = client.post("/leads", json=payload)
    assert response.status_code == 422


def test_list_leads():
    client.post("/leads", json=VALID_LEAD)
    response = client.get("/leads")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_get_lead_by_id():
    # Create a lead first
    response = client.post("/leads", json=VALID_LEAD)
    lead_id = response.json()["lead"]["id"]

    response = client.get(f"/leads/{lead_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == lead_id
    assert data["name"] == "Test User"


def test_get_lead_not_found():
    response = client.get("/leads/99999")
    assert response.status_code == 404
