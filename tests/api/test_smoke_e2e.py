"""Smoke test: end-to-end MVP circuit proof.

Validates the full lead lifecycle in a single sequential test:
intake → operational surface → outcome recording → history → intelligence → export
"""

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


def test_full_lead_lifecycle_circuit():
    """Single test proving the full MVP circuit works end-to-end."""

    # 1. Create lead via webhook intake with structured notes that produce a reviewable score
    #    Scoring: base 20 + 5 (has notes) + 10 (phone) + 10 (high-value boat) = 45 → review_manually
    resp = client.post("/leads/webhook/smoke-test", json={
        "name": "E2E Smoke",
        "email": "smoke@e2e-test.com",
        "notes": (
            "Teléfono: +34600000000\n"
            "Interés: velero\n"
            "Mensaje: Quiero vender mi velero de 12 metros en Barcelona"
        ),
    })
    assert resp.status_code == 200, f"Intake failed: {resp.text}"
    data = resp.json()
    assert data["status"] == "accepted"
    lead_id = data["lead_id"]
    assert isinstance(lead_id, int)

    # 2. Verify lead appears in operational surface (daily-actions review or client-ready)
    daily = client.get("/internal/daily-actions").json()
    all_lead_ids = (
        [i["lead_id"] for i in daily["top_review"]]
        + [i["lead_id"] for i in daily["top_client_ready"]]
    )
    assert lead_id in all_lead_ids, (
        f"Lead {lead_id} not visible in daily-actions after creation"
    )

    # 3. Record first outcome: contacted
    resp = client.post("/internal/outcomes", json={
        "lead_id": lead_id,
        "outcome": "contacted",
        "recorded_by": "smoke_test",
    })
    assert resp.status_code == 201

    # 4. Record second outcome: lost with loss_reason
    resp = client.post("/internal/outcomes", json={
        "lead_id": lead_id,
        "outcome": "lost",
        "loss_reason": "price",
        "reason": "Budget too low",
        "recorded_by": "smoke_test",
    })
    assert resp.status_code == 201
    assert resp.json()["loss_reason"] == "price"

    # 5. Verify outcome history shows both changes
    hist = client.get(f"/internal/outcomes/history/{lead_id}").json()
    assert hist["total_changes"] == 2
    assert hist["history"][0]["outcome"] == "contacted"
    assert hist["history"][1]["outcome"] == "lost"
    assert hist["current"]["outcome"] == "lost"
    assert hist["current"]["loss_reason"] == "price"

    # 6. Verify intelligence surfaces reflect the outcome
    # 6a. Source intelligence includes this source
    si = client.get("/internal/source-intelligence", params={"source": "webhook:smoke-test"}).json()
    assert si["totals"]["leads"] >= 1

    # 6b. Loss analysis includes the loss_reason
    la = client.get("/internal/intelligence/loss-analysis", params={"source": "webhook:smoke-test"}).json()
    assert la["total_lost"] >= 1
    assert la["by_reason"]["price"] >= 1

    # 6c. Score effectiveness includes this lead in a bucket
    se = client.get("/internal/intelligence/score-effectiveness", params={"source": "webhook:smoke-test"}).json()
    total_in_buckets = sum(b["total"] for b in se["buckets"])
    assert total_in_buckets >= 1

    # 7. Verify machine-consumable export works (CSV responds, may be empty for this lead since outcome != no_answer)
    csv_resp = client.get("/internal/followup-automation/export.csv")
    assert csv_resp.status_code == 200
    assert csv_resp.headers["content-type"].startswith("text/csv")
