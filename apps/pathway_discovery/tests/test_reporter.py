"""Tests for report generation."""

import json
import os
import tempfile

from apps.pathway_discovery.reporter import (
    generate_report, generate_json, _persist_reports, _is_bootstrap,
    _load_previous_data, _classify_drift, REPORT_SCHEMA_VERSION,
)
from apps.pathway_discovery.schemas import (
    CandidatePathway, CandidateType, ModuleDrift, ModuleRegistryEntry, PathwayRecommendation,
)


def _kd(debt_age=1, debt_status="active"):
    return PathwayRecommendation(
        recommendation_id="PR-KD",
        candidate=CandidatePathway(candidate_id="CP-KD", candidate_type=CandidateType.PROHIBITED_CONNECTION,
                                   description="[KNOWN DEBT]", occurrence_count=5, stable_fingerprint="fp-kd"),
        score=40.0, review_bucket="known_debt", governance_status="KNOWN_DEBT",
        debt_status=debt_status, debt_age=debt_age,
        in_review_queue=debt_status == "review_due", operator_status="unreviewed" if debt_status == "review_due" else "",
        why_now="debt review threshold" if debt_status == "review_due" else "",
        intervention_hint="Review extraction" if debt_status == "review_due" else "",
    )


def _wl(age=1, escalated=False, severity=30.0, in_queue=False):
    return PathwayRecommendation(
        recommendation_id="PR-W",
        candidate=CandidatePathway(candidate_id="CP-W", candidate_type=CandidateType.LONG_PATH,
                                   description="chain a->b->c", modules_involved=["a", "b", "c"],
                                   confidence=0.4, raw_confidence=0.7, orchestrator_penalty=0.3,
                                   stable_fingerprint="fp-w"),
        score=50.0, review_bucket="watchlist", governance_status="DEFERRED",
        watchlist_age=age, escalated_watchlist=escalated,
        watchlist_severity_score=severity,
        in_review_queue=in_queue or escalated,
        operator_status="unreviewed" if (in_queue or escalated) else "",
        why_now="persistent, escalated" if escalated else "",
        intervention_hint="Evaluate orchestration" if escalated else "",
    )


# --- Wording ---
def test_no_clean_when_debt():
    assert "Architecture is clean" not in generate_report([_kd()], [], [], [], [])

def test_clean_when_no_debt():
    assert "Architecture is clean" in generate_report([], [], [], [], [])


# --- Review Queue section ---
def test_review_queue_appears_when_items():
    report = generate_report([_wl(age=5, escalated=True, severity=70, in_queue=True)], [], [], [], [])
    assert "## Review Queue" in report
    assert "WATCHLIST-ESCALATED" in report

def test_review_queue_shows_why_now():
    report = generate_report([_wl(age=5, escalated=True, severity=70, in_queue=True)], [], [], [], [])
    assert "Why now" in report

def test_review_queue_shows_hint():
    report = generate_report([_wl(age=5, escalated=True, severity=70, in_queue=True)], [], [], [], [])
    assert "Hint" in report

def test_review_queue_absent_when_no_items():
    report = generate_report([_wl(age=1, escalated=False)], [], [], [], [])
    assert "## Review Queue" not in report

def test_review_queue_debt_review_due():
    report = generate_report([_kd(debt_age=5, debt_status="review_due")], [], [], [], [])
    assert "## Review Queue" in report
    assert "KNOWN-DEBT-REVIEW-DUE" in report


# --- Top Structural Observations ---
def test_observations_prefers_queue():
    esc = _wl(age=5, escalated=True, severity=70, in_queue=True)
    plain = _wl(age=1)
    plain.candidate.stable_fingerprint = "fp-other"
    plain.recommendation_id = "PR-W2"
    report = generate_report([plain, esc], [], [], [], [])
    obs = report.split("## Top Structural Observations")[1].split("##")[0]
    first_line = [l for l in obs.strip().split("\n") if l.startswith("1.")][0]
    assert "REVIEW-QUEUE" in first_line


# --- Debt display ---
def test_shows_review_due():
    report = generate_report([_kd(debt_age=5, debt_status="review_due")], [], [], [], [])
    assert "review_due" in report


# --- Delta ---
def test_delta_with_previous():
    prev = {"summary": {"candidates": 7, "known_debt": 1, "backlog": 0, "watchlist": 3, "prohibited_new": 0},
            "graph_health": {"max_fan_out_runtime": 7, "max_fan_in": 5}}
    assert "candidates: 7 -> 0" in generate_report([], [], [], [], [], previous_data=prev)

def test_delta_no_previous():
    assert "No previous audit found" in generate_report([], [], [], [], [])

def test_delta_missing_keys():
    assert "?" not in generate_report([], [], [], [], [], previous_data={"summary": {"candidates": 5}})


# --- Drift ---
def test_drift_stable():
    assert _classify_drift(3, 3, 2, 2) == "stable"

def test_drift_notable():
    assert _classify_drift(4, 5, 2, 2) == "notable_drift"

def test_drift_critical():
    assert _classify_drift(7, 8, 2, 2) == "critical_drift"

def test_drift_report_shows_notable():
    report = generate_report([], [], [], [], [], module_drifts=[ModuleDrift("a", 4, 6, 2, 2, "notable_drift")])
    assert "notable_drift" in report

def test_drift_hides_mild():
    report = generate_report([], [], [], [], [], module_drifts=[ModuleDrift("a", 3, 4, 2, 2, "mild_drift")])
    assert "No notable module drift" in report


# --- JSON ---
def test_json_schema_version():
    assert json.loads(generate_json([], [], [], [], []))["report_schema_version"] == REPORT_SCHEMA_VERSION

def test_json_has_review_queue_state():
    rec = _wl(age=5, escalated=True, in_queue=True)
    js = json.loads(generate_json([rec], [], [], [], []))
    assert "review_queue_state" in js
    assert js["review_queue_state"]["fp-w"]["operator_status"] == "unreviewed"

def test_json_has_why_now():
    rec = _wl(age=5, escalated=True, in_queue=True)
    js = json.loads(generate_json([rec], [], [], [], []))
    assert js["recommendations"][0]["why_now"] != ""

def test_json_has_intervention_hint():
    rec = _wl(age=5, escalated=True, in_queue=True)
    js = json.loads(generate_json([rec], [], [], [], []))
    assert js["recommendations"][0]["intervention_hint"] != ""

def test_json_has_in_review_queue():
    rec = _wl(age=5, escalated=True, in_queue=True)
    js = json.loads(generate_json([rec], [], [], [], []))
    assert js["recommendations"][0]["in_review_queue"] is True

def test_json_drift():
    js = json.loads(generate_json([], [], [], [], [], [ModuleDrift("a", 3, 5, 2, 2, "notable_drift")]))
    assert js["module_drift"][0]["classification"] == "notable_drift"

def test_json_debt_state():
    js = json.loads(generate_json([_kd(debt_age=4)], [], [], [], []))
    assert "debt_state" in js


# --- Persist/load ---
def test_persist():
    with tempfile.TemporaryDirectory() as t:
        md, js = _persist_reports("# md", '{}', t)
        assert os.path.isfile(md) and os.path.isfile(js)

def test_bootstrap():
    assert _is_bootstrap("apps.api.main") and not _is_bootstrap("apps.api.routes.leads")
