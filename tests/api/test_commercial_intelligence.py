"""Tests for Commercial Intelligence / Data Engine Core — Phase A.

Covers:
- POST /internal/outcomes extended (loss_reason, recorded_by, idempotency, transaction)
- GET /internal/outcomes/history/{lead_id}
- Backfill behavior
"""

import tempfile

import apps.api.db as db_module

# Isolated temp DB — must happen before importing app
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
db_module.DATABASE_PATH = _tmp.name
db_module.reset_db()
db_module.init_db()

from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)


def _create_lead(name: str = "CI Test", email: str | None = None, source: str = "ci_test") -> int:
    """Create a lead and return its ID."""
    if email is None:
        import uuid
        email = f"ci_{uuid.uuid4().hex[:8]}@test.com"
    resp = client.post("/leads", json={"name": name, "email": email, "source": source})
    assert resp.status_code in (200, 201, 409), resp.text
    data = resp.json()
    # Handle both response shapes
    if "id" in data:
        return data["id"]
    if "lead" in data and "id" in data["lead"]:
        return data["lead"]["id"]
    # Duplicate — fetch by listing
    leads = client.get("/leads", params={"source": source}).json()
    for lead in leads:
        if lead["email"] == email:
            return lead["id"]
    raise AssertionError(f"Could not find lead with email {email}")


# --- POST /internal/outcomes: backward compat ---

def test_outcome_backward_compat_no_new_fields():
    """Existing callers without loss_reason/recorded_by still work."""
    lid = _create_lead(email="compat@ci.com")
    resp = client.post("/internal/outcomes", json={
        "lead_id": lid,
        "outcome": "contacted",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["outcome"] == "contacted"
    assert data["loss_reason"] is None
    assert data["recorded_by"] == "system"


# --- POST /internal/outcomes: loss_reason ---

def test_outcome_loss_reason_accepted_on_lost():
    lid = _create_lead(email="lrlost@ci.com")
    resp = client.post("/internal/outcomes", json={
        "lead_id": lid,
        "outcome": "lost",
        "loss_reason": "price",
    })
    assert resp.status_code == 201
    assert resp.json()["loss_reason"] == "price"


def test_outcome_loss_reason_null_on_non_lost():
    """loss_reason silently set to NULL when outcome != lost."""
    lid = _create_lead(email="lrnon@ci.com")
    resp = client.post("/internal/outcomes", json={
        "lead_id": lid,
        "outcome": "qualified",
        "loss_reason": "price",
    })
    assert resp.status_code == 201
    assert resp.json()["loss_reason"] is None


def test_outcome_loss_reason_invalid_422():
    lid = _create_lead(email="lrinv@ci.com")
    resp = client.post("/internal/outcomes", json={
        "lead_id": lid,
        "outcome": "lost",
        "loss_reason": "bad_fit",  # not a valid loss_reason
    })
    assert resp.status_code == 422


# --- POST /internal/outcomes: recorded_by ---

def test_outcome_recorded_by_default_system():
    lid = _create_lead(email="rbdef@ci.com")
    resp = client.post("/internal/outcomes", json={
        "lead_id": lid,
        "outcome": "contacted",
    })
    assert resp.json()["recorded_by"] == "system"


def test_outcome_recorded_by_custom():
    lid = _create_lead(email="rbcust@ci.com")
    resp = client.post("/internal/outcomes", json={
        "lead_id": lid,
        "outcome": "contacted",
        "recorded_by": "didac",
    })
    assert resp.json()["recorded_by"] == "didac"


# --- POST /internal/outcomes: idempotency ---

def test_outcome_idempotent_no_duplicate_history():
    """Identical payload twice → only 1 history row."""
    lid = _create_lead(email="idemp@ci.com")
    payload = {"lead_id": lid, "outcome": "contacted", "reason": "first call"}

    resp1 = client.post("/internal/outcomes", json=payload)
    assert resp1.status_code == 201

    resp2 = client.post("/internal/outcomes", json=payload)
    assert resp2.status_code == 201

    # Check history has exactly 1 entry
    hist = client.get(f"/internal/outcomes/history/{lid}")
    assert hist.json()["total_changes"] == 1


def test_outcome_idempotent_returns_current():
    """Idempotent call returns current snapshot without updating recorded_at."""
    lid = _create_lead(email="idret@ci.com")
    payload = {"lead_id": lid, "outcome": "won"}

    resp1 = client.post("/internal/outcomes", json=payload)
    ts1 = resp1.json()["recorded_at"]

    resp2 = client.post("/internal/outcomes", json=payload)
    ts2 = resp2.json()["recorded_at"]

    assert ts1 == ts2  # recorded_at unchanged



def test_outcome_idempotent_different_recorded_by():
    """recorded_by does NOT participate in idempotency.

    Same (outcome, loss_reason, reason, notes) but different recorded_by
    → no-op, same recorded_at, same current row, single history row.
    """
    lid = _create_lead(email="idrb@ci.com")
    base = {"lead_id": lid, "outcome": "lost", "loss_reason": "price", "reason": "too expensive", "notes": "called twice"}

    resp1 = client.post("/internal/outcomes", json={**base, "recorded_by": "didac"})
    assert resp1.status_code == 201
    ts1 = resp1.json()["recorded_at"]
    rb1 = resp1.json()["recorded_by"]

    resp2 = client.post("/internal/outcomes", json={**base, "recorded_by": "pau"})
    assert resp2.status_code == 201
    ts2 = resp2.json()["recorded_at"]
    rb2 = resp2.json()["recorded_by"]

    # No-op: same timestamp, same recorded_by (unchanged)
    assert ts1 == ts2
    assert rb1 == rb2 == "didac"

    # Single history row
    hist = client.get(f"/internal/outcomes/history/{lid}")
    assert hist.json()["total_changes"] == 1


def test_outcome_rollback_on_history_insert_failure():
    """If history INSERT fails, the snapshot upsert must be rolled back — no partial state.

    Strategy: rename lead_outcome_history to force the second INSERT to fail,
    then verify the snapshot was NOT changed (rollback worked).
    """
    lid = _create_lead(email="rollback@ci.com")
    # Record a baseline outcome
    client.post("/internal/outcomes", json={"lead_id": lid, "outcome": "contacted"})

    db = db_module.get_db()
    before = db.execute(
        "SELECT outcome FROM lead_outcomes WHERE lead_id = ?", (lid,)
    ).fetchone()
    assert before["outcome"] == "contacted"

    history_count_before = db.execute(
        "SELECT COUNT(*) FROM lead_outcome_history WHERE lead_id = ?", (lid,)
    ).fetchone()[0]

    # Sabotage: rename the history table so the INSERT fails
    db.execute("ALTER TABLE lead_outcome_history RENAME TO _loh_broken")
    db.commit()

    # Use a non-raising client so we get 500 instead of an exception
    from starlette.testclient import TestClient as _TC
    quiet_client = _TC(app, raise_server_exceptions=False)

    try:
        resp = quiet_client.post("/internal/outcomes", json={
            "lead_id": lid, "outcome": "won",
        })
        # Endpoint should return 500 (history INSERT failed)
        assert resp.status_code == 500
    finally:
        # Restore the table regardless of test outcome
        db.execute("ALTER TABLE _loh_broken RENAME TO lead_outcome_history")
        db.commit()

    # Verify rollback: snapshot must still be "contacted", not "won"
    after = db.execute(
        "SELECT outcome FROM lead_outcomes WHERE lead_id = ?", (lid,)
    ).fetchone()
    assert after["outcome"] == "contacted", (
        f"Partial state: snapshot changed to '{after['outcome']}' without history"
    )

    # History count unchanged
    history_count_after = db.execute(
        "SELECT COUNT(*) FROM lead_outcome_history WHERE lead_id = ?", (lid,)
    ).fetchone()[0]
    assert history_count_after == history_count_before


# --- POST /internal/outcomes: history creation ---

def test_outcome_change_creates_history():
    """Changing outcome creates a new history row."""
    lid = _create_lead(email="hist@ci.com")

    client.post("/internal/outcomes", json={"lead_id": lid, "outcome": "contacted"})
    client.post("/internal/outcomes", json={"lead_id": lid, "outcome": "qualified"})
    client.post("/internal/outcomes", json={"lead_id": lid, "outcome": "won"})

    hist = client.get(f"/internal/outcomes/history/{lid}")
    data = hist.json()
    assert data["total_changes"] == 3
    assert data["history"][0]["outcome"] == "contacted"
    assert data["history"][1]["outcome"] == "qualified"
    assert data["history"][2]["outcome"] == "won"
    assert data["current"]["outcome"] == "won"


def test_outcome_write_updates_snapshot_and_history():
    """A single outcome write updates both lead_outcomes and lead_outcome_history."""
    lid = _create_lead(email="txn@ci.com")
    client.post("/internal/outcomes", json={"lead_id": lid, "outcome": "contacted"})

    # Verify lead_outcomes has the entry
    resp = client.get(f"/internal/outcomes/history/{lid}")
    data = resp.json()
    assert data["current"] is not None
    assert data["current"]["outcome"] == "contacted"
    assert len(data["history"]) == 1
    assert data["history"][0]["outcome"] == "contacted"


# --- GET /internal/outcomes/history/{lead_id} ---

def test_history_endpoint_shape():
    lid = _create_lead(email="hshape@ci.com")
    client.post("/internal/outcomes", json={"lead_id": lid, "outcome": "contacted"})

    resp = client.get(f"/internal/outcomes/history/{lid}")
    assert resp.status_code == 200
    data = resp.json()
    assert "lead_id" in data
    assert "current" in data
    assert "history" in data
    assert "total_changes" in data
    assert data["lead_id"] == lid

    entry = data["history"][0]
    for field in ("outcome", "loss_reason", "reason", "notes", "recorded_by", "recorded_at"):
        assert field in entry


def test_history_chronological_order():
    lid = _create_lead(email="hchr@ci.com")
    client.post("/internal/outcomes", json={"lead_id": lid, "outcome": "contacted"})
    client.post("/internal/outcomes", json={"lead_id": lid, "outcome": "qualified"})

    resp = client.get(f"/internal/outcomes/history/{lid}")
    history = resp.json()["history"]
    assert history[0]["outcome"] == "contacted"
    assert history[1]["outcome"] == "qualified"
    assert history[0]["recorded_at"] <= history[1]["recorded_at"]


def test_history_404_unknown_lead():
    resp = client.get("/internal/outcomes/history/999999")
    assert resp.status_code == 404


def test_history_empty_no_outcomes():
    lid = _create_lead(email="hnone@ci.com")
    resp = client.get(f"/internal/outcomes/history/{lid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["current"] is None
    assert data["history"] == []
    assert data["total_changes"] == 0


def test_history_backfill_row_present():
    """Backfill creates exactly 1 history row for a pre-existing outcome, idempotently."""
    db = db_module.get_db()

    # 1. Create a lead directly
    lid = _create_lead(email="bfill@ci.com")

    # 2. Insert outcome directly into lead_outcomes (simulates pre-migration data)
    #    WITHOUT creating a history row — this is the state backfill targets.
    db.execute(
        "INSERT INTO lead_outcomes (lead_id, outcome, reason, notes, recorded_by, recorded_at) "
        "VALUES (?, 'contacted', 'legacy', NULL, 'system', '2026-01-01T00:00:00')",
        (lid,),
    )
    db.commit()

    # Confirm: no history row yet
    count_before = db.execute(
        "SELECT COUNT(*) FROM lead_outcome_history WHERE lead_id = ?", (lid,)
    ).fetchone()[0]
    assert count_before == 0

    # 3. Run backfill (via init_db which is idempotent)
    db_module.init_db()

    # 4. Verify exactly 1 history row with recorded_by='backfill'
    rows = db.execute(
        "SELECT outcome, recorded_by FROM lead_outcome_history WHERE lead_id = ? ORDER BY id",
        (lid,),
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["outcome"] == "contacted"
    assert rows[0]["recorded_by"] == "backfill"

    # 5. Run backfill again — must not duplicate
    db_module.init_db()
    count_after = db.execute(
        "SELECT COUNT(*) FROM lead_outcome_history WHERE lead_id = ?", (lid,)
    ).fetchone()[0]
    assert count_after == 1


# =============================================================================
# Phase B — Intelligence endpoints
# =============================================================================


def _setup_intelligence_data():
    """Create diverse leads with outcomes for intelligence tests.

    Creates leads across 2 sources, various scores, various outcomes.
    Records history via POST /internal/outcomes to ensure history rows exist.
    """
    leads = [
        # source=alpha, varying scores and outcomes
        ("A1", "a1@intel.com", "alpha", "notes score_override_80", "won", None),
        ("A2", "a2@intel.com", "alpha", "notes score_override_75", "lost", "price"),
        ("A3", "a3@intel.com", "alpha", "notes score_override_60", "lost", "timing"),
        ("A4", "a4@intel.com", "alpha", "notes score_override_45", "qualified", None),
        ("A5", "a5@intel.com", "alpha", "notes score_override_25", "no_answer", None),
        ("A6", "a6@intel.com", "alpha", "notes score_override_20", "bad_fit", None),
        ("A7", "a7@intel.com", "alpha", "notes score_override_15", "contacted", None),
        ("A8", "a8@intel.com", "alpha", "notes score_override_10", "lost", None),  # unspecified loss_reason
        # source=beta
        ("B1", "b1@intel.com", "beta", "notes score_override_90", "won", None),
        ("B2", "b2@intel.com", "beta", "notes score_override_85", "won", None),
        ("B3", "b3@intel.com", "beta", "notes score_override_35", "lost", "competitor"),
        ("B4", "b4@intel.com", "beta", "notes score_override_30", "no_answer", None),
    ]

    created_ids = []
    for name, email, source, notes, outcome, loss_reason in leads:
        lid = _create_lead(name=name, email=email, source=source)
        created_ids.append(lid)

        # First record as 'contacted' to build history (for stage progression tests)
        client.post("/internal/outcomes", json={
            "lead_id": lid, "outcome": "contacted",
        })

        # Then record final outcome (if different from contacted)
        if outcome != "contacted":
            payload: dict = {"lead_id": lid, "outcome": outcome}
            if loss_reason:
                payload["loss_reason"] = loss_reason
            client.post("/internal/outcomes", json=payload)

    return created_ids


_intel_data_created = False


def _ensure_intelligence_data():
    global _intel_data_created
    if not _intel_data_created:
        _setup_intelligence_data()
        _intel_data_created = True


# --- Loss Analysis ---


def test_loss_analysis_distribution():
    _ensure_intelligence_data()
    # Filter by alpha to avoid interference from Phase A test data
    resp = client.get("/internal/intelligence/loss-analysis", params={"source": "alpha"})
    assert resp.status_code == 200
    data = resp.json()

    assert data["total_lost"] == 3  # A2(price), A3(timing), A8(unspecified)
    reasons = data["by_reason"]
    assert reasons["price"] == 1
    assert reasons["timing"] == 1
    assert reasons["unspecified"] == 1  # A8 has no loss_reason
    assert data["source_filter"] == "alpha"


def test_loss_analysis_unspecified_count():
    _ensure_intelligence_data()
    resp = client.get("/internal/intelligence/loss-analysis")
    data = resp.json()
    assert data["by_reason"]["unspecified"] >= 1


def test_loss_analysis_top_reason_and_by_source():
    _ensure_intelligence_data()
    resp = client.get("/internal/intelligence/loss-analysis")
    data = resp.json()

    # top_reason excludes unspecified
    assert data["top_reason"] is not None
    assert data["top_reason"] != "unspecified"

    # by_source has at least 2 sources
    assert len(data["by_source"]) >= 2

    # Filtered by source
    resp_alpha = client.get("/internal/intelligence/loss-analysis", params={"source": "alpha"})
    data_alpha = resp_alpha.json()
    assert data_alpha["source_filter"] == "alpha"
    assert len(data_alpha["by_source"]) == 1
    assert data_alpha["by_source"][0]["source"] == "alpha"


# --- Score Effectiveness ---


def test_score_effectiveness_buckets_structure():
    _ensure_intelligence_data()
    resp = client.get("/internal/intelligence/score-effectiveness")
    assert resp.status_code == 200
    data = resp.json()

    assert len(data["buckets"]) == 4
    ranges = [b["range"] for b in data["buckets"]]
    assert ranges == ["0-30", "31-50", "51-70", "71-100"]

    for bucket in data["buckets"]:
        for field in ("total", "contacted_or_beyond", "qualified_or_beyond",
                       "won", "lost", "bad_fit", "no_answer",
                       "contact_rate", "qualification_rate", "win_rate_on_terminal"):
            assert field in bucket


def test_score_effectiveness_contacted_or_beyond_from_history():
    """contacted_or_beyond must come from history (ever reached stage), not just current."""
    _ensure_intelligence_data()
    # Use source filter to isolate test data from Phase A leftovers
    resp = client.get("/internal/intelligence/score-effectiveness", params={"source": "alpha"})
    data = resp.json()

    # All 8 alpha leads had 'contacted' recorded in history first
    total_contacted = sum(b["contacted_or_beyond"] for b in data["buckets"])
    assert total_contacted == data["total_with_outcomes"]


def test_score_effectiveness_qualified_or_beyond_from_history():
    """qualified_or_beyond derived from history — leads that ever reached qualified/won/lost/bad_fit."""
    _ensure_intelligence_data()
    # Use source filter to isolate
    resp = client.get("/internal/intelligence/score-effectiveness", params={"source": "alpha"})
    data = resp.json()

    # Alpha leads whose outcome is in qualified_or_beyond set (qualified, won, lost, bad_fit):
    # A1(won), A2(lost), A3(lost), A4(qualified), A6(bad_fit), A8(lost) = 6
    # A5(no_answer) and A7(contacted) are NOT in qualified_or_beyond
    total_qualified = sum(b["qualified_or_beyond"] for b in data["buckets"])
    assert total_qualified == 6


def test_score_effectiveness_rates_correct():
    _ensure_intelligence_data()
    resp = client.get("/internal/intelligence/score-effectiveness")
    data = resp.json()

    for bucket in data["buckets"]:
        total = bucket["total"]
        if total > 0:
            assert bucket["contact_rate"] == round(bucket["contacted_or_beyond"] / total, 2)
            assert bucket["qualification_rate"] == round(bucket["qualified_or_beyond"] / total, 2)
        terminal = bucket["won"] + bucket["lost"] + bucket["bad_fit"]
        if terminal > 0:
            assert bucket["win_rate_on_terminal"] == round(bucket["won"] / terminal, 2)


def test_score_effectiveness_source_filter():
    _ensure_intelligence_data()
    resp = client.get("/internal/intelligence/score-effectiveness", params={"source": "beta"})
    data = resp.json()
    assert data["source_filter"] == "beta"
    total = sum(b["total"] for b in data["buckets"])
    assert total == 4  # B1, B2, B3, B4


def test_score_effectiveness_signal_insufficient():
    """With fewer than 10 outcomes, signal is insufficient_data."""
    resp = client.get("/internal/intelligence/score-effectiveness", params={"source": "beta"})
    data = resp.json()
    # beta has only 4 leads
    assert data["scoring_accuracy_signal"] == "insufficient_data"


# --- Cohorts ---


def test_cohorts_monthly_grouping():
    _ensure_intelligence_data()
    resp = client.get("/internal/intelligence/cohorts", params={"months": 1})
    assert resp.status_code == 200
    data = resp.json()

    assert data["months_requested"] == 1
    assert len(data["cohorts"]) == 1

    cohort = data["cohorts"][0]
    for field in ("month", "leads_created", "with_outcomes", "contacted_or_beyond",
                   "qualified_or_beyond", "won", "lost", "bad_fit", "no_answer",
                   "avg_score", "contact_rate", "qualification_rate", "win_rate_on_terminal"):
        assert field in cohort


def test_cohorts_source_filter():
    _ensure_intelligence_data()
    resp = client.get("/internal/intelligence/cohorts", params={"source": "beta", "months": 1})
    data = resp.json()
    assert data["source_filter"] == "beta"

    cohort = data["cohorts"][0]
    # Beta has 4 leads
    assert cohort["leads_created"] == 4


def test_cohorts_rates_from_history():
    """Cohort contacted_or_beyond must come from history."""
    _ensure_intelligence_data()
    # Filter by alpha to isolate from Phase A test data
    resp = client.get("/internal/intelligence/cohorts", params={"months": 1, "source": "alpha"})
    data = resp.json()

    cohort = data["cohorts"][0]
    # All 8 alpha leads were contacted first in history
    assert cohort["contacted_or_beyond"] == cohort["with_outcomes"]
    # 6 reached qualified_or_beyond (A1-won, A2-lost, A3-lost, A4-qualified, A6-bad_fit, A8-lost)
    assert cohort["qualified_or_beyond"] == 6
