"""Tests for review queue decision lifecycle (V1.8)."""

import json

from apps.pathway_discovery.reporter import generate_report, generate_json
from apps.pathway_discovery.schemas import CandidatePathway, CandidateType, PathwayRecommendation
from apps.pathway_discovery.scorer import (
    score_candidates, compute_fingerprint, merge_review_state,
)


def _make_watchlist(**kw) -> CandidatePathway:
    defaults = dict(
        candidate_id="CP-W", candidate_type=CandidateType.LONG_PATH,
        description="chain a->b->c", modules_involved=["a", "b", "c"],
        call_frequency="per_request", confidence=0.4, raw_confidence=0.7,
        orchestrator_penalty=0.3, estimated_effort="medium",
        touches_protected=True, risk_level="medium",
    )
    defaults.update(kw)
    return CandidatePathway(**defaults)


def _make_debt(**kw) -> CandidatePathway:
    defaults = dict(
        candidate_id="CP-D", candidate_type=CandidateType.PROHIBITED_CONNECTION,
        description="[KNOWN DEBT: x]", modules_involved=["routes", "db"],
        risk_level="medium", touches_protected=True,
        call_frequency="per_request", confidence=0.95, raw_confidence=0.95,
    )
    defaults.update(kw)
    return CandidatePathway(**defaults)


# --- merge_review_state ---

def test_merge_preserves_active():
    c = _make_watchlist()
    fp = compute_fingerprint(c)
    recs = score_candidates([c], previous_watchlist={fp: 4})
    state = merge_review_state(recs, {})
    assert fp in state
    assert state[fp]["inactive"] is False


def test_merge_marks_missing_inactive():
    c = _make_watchlist()
    fp = compute_fingerprint(c)
    # Previous had an item, current has none in queue
    prev = {fp: {"operator_status": "monitor", "operator_note": "tracking", "inactive": False,
                 "last_bucket": "watchlist", "last_description": "old desc"}}
    recs = score_candidates([], previous_watchlist={})  # No candidates
    state = merge_review_state(recs, prev)
    assert fp in state
    assert state[fp]["inactive"] is True
    assert state[fp]["operator_status"] == "monitor"  # Preserved


def test_merge_revives_reappearing():
    c = _make_watchlist()
    fp = compute_fingerprint(c)
    prev = {fp: {"operator_status": "keep", "operator_note": "accepted", "inactive": True,
                 "last_bucket": "watchlist", "last_description": "old"}}
    recs = score_candidates([c], previous_watchlist={fp: 4}, previous_review_queue=prev)
    state = merge_review_state(recs, prev)
    assert fp in state
    assert state[fp]["inactive"] is False
    assert state[fp]["operator_status"] == "keep"  # Restored from previous


# --- mark_missing / revive helpers ---

# --- resolved item lifecycle ---

def test_resolved_stays_persisted_when_absent():
    c = _make_watchlist()
    fp = compute_fingerprint(c)
    prev = {fp: {"operator_status": "resolved", "operator_note": "done",
                 "decision_reason": "fixed in v2", "reviewed_at": "2026-03-18",
                 "inactive": False, "last_bucket": "watchlist", "last_description": "chain"}}
    # Finding no longer in current candidates
    recs = score_candidates([], previous_watchlist={})
    state = merge_review_state(recs, prev)
    assert fp in state
    assert state[fp]["inactive"] is True
    assert state[fp]["operator_status"] == "resolved"


def test_resolved_item_not_in_active_queue():
    c = _make_watchlist()
    fp = compute_fingerprint(c)
    prev = {fp: {"operator_status": "resolved", "operator_note": "done",
                 "decision_reason": "fixed", "reviewed_at": "2026-03-18"}}
    recs = score_candidates([c], previous_watchlist={fp: 4}, previous_review_queue=prev)
    assert recs[0].in_review_queue is False  # resolved = not active


# --- Decision Log ---

def test_decision_log_appears_for_reviewed_items():
    rec = PathwayRecommendation(
        recommendation_id="PR-1",
        candidate=CandidatePathway(candidate_id="CP-1", candidate_type=CandidateType.LONG_PATH,
                                   description="test", stable_fingerprint="fp-rev"),
        score=50.0, review_bucket="watchlist", governance_status="DEFERRED",
        operator_status="monitor", operator_note="watching", decision_reason="looks stable",
        reviewed_at="2026-03-18",
    )
    report = generate_report([rec], [], [], [], [])
    assert "## Decision Log" in report
    assert "monitor" in report
    assert "looks stable" in report


def test_decision_log_shows_inactive_from_state():
    full_state = {
        "fp-old": {
            "operator_status": "resolved", "operator_note": "fixed",
            "decision_reason": "done", "reviewed_at": "2026-03-17",
            "inactive": True, "last_bucket": "watchlist",
            "last_description": "old chain finding",
        }
    }
    report = generate_report([], [], [], [], [], full_review_state=full_state)
    assert "## Decision Log" in report
    assert "inactive" in report.lower()
    assert "fp-old"[:8] in report


def test_decision_log_absent_when_nothing():
    report = generate_report([], [], [], [], [])
    assert "## Decision Log" not in report


# --- Active Review Queue excludes ---

def test_active_queue_excludes_inactive():
    rec = PathwayRecommendation(
        recommendation_id="PR-1",
        candidate=CandidatePathway(candidate_id="CP-1", candidate_type=CandidateType.LONG_PATH,
                                   description="test", stable_fingerprint="fp-1"),
        score=50.0, review_bucket="watchlist",
        in_review_queue=True, inactive=True, operator_status="monitor",
    )
    report = generate_report([rec], [], [], [], [])
    # Should NOT appear in active Review Queue
    if "## Review Queue" in report:
        queue_section = report.split("## Review Queue")[1].split("##")[0]
        assert "fp-1"[:8] not in queue_section


def test_active_queue_excludes_resolved():
    rec = PathwayRecommendation(
        recommendation_id="PR-1",
        candidate=CandidatePathway(candidate_id="CP-1", candidate_type=CandidateType.LONG_PATH,
                                   description="test", stable_fingerprint="fp-1"),
        score=50.0, review_bucket="watchlist",
        in_review_queue=False, operator_status="resolved",  # resolved = not in_review_queue
    )
    report = generate_report([rec], [], [], [], [])
    if "## Review Queue" in report:
        queue_section = report.split("## Review Queue")[1].split("##")[0]
        assert "fp-1"[:8] not in queue_section


# --- JSON persistence ---

def test_json_retains_inactive_entries():
    full_state = {
        "fp-active": {"operator_status": "unreviewed", "inactive": False},
        "fp-gone": {"operator_status": "monitor", "inactive": True, "operator_note": "was here"},
    }
    js = json.loads(generate_json([], [], [], [], [], full_review_state=full_state))
    rqs = js["review_queue_state"]
    assert "fp-active" in rqs
    assert "fp-gone" in rqs
    assert rqs["fp-gone"]["inactive"] is True
    assert rqs["fp-gone"]["operator_note"] == "was here"


def test_json_retains_resolved_entries():
    full_state = {
        "fp-done": {"operator_status": "resolved", "inactive": True, "decision_reason": "fixed"},
    }
    js = json.loads(generate_json([], [], [], [], [], full_review_state=full_state))
    assert js["review_queue_state"]["fp-done"]["operator_status"] == "resolved"
