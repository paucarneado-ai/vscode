"""Tests for the scoring engine."""

from apps.pathway_discovery.schemas import CandidatePathway, CandidateType, ModuleDrift
from apps.pathway_discovery.scorer import score_candidates, compute_fingerprint, compute_watchlist_severity


def _make_candidate(**overrides) -> CandidatePathway:
    defaults = dict(
        candidate_id="CP-TEST", candidate_type=CandidateType.REDUNDANT_TRANSFORM,
        description="test", modules_involved=["mod_a", "mod_b"], evidence=["file.py:10"],
        call_frequency="per_request", confidence=0.9, raw_confidence=0.9,
        orchestrator_penalty=0.0, confidence_reason="test",
        estimated_effort="small", risk_level="low", touches_protected=False,
    )
    defaults.update(overrides)
    return CandidatePathway(**defaults)


def _make_watchlist(**overrides) -> CandidatePathway:
    defaults = dict(
        candidate_type=CandidateType.LONG_PATH, confidence=0.4, raw_confidence=0.7,
        orchestrator_penalty=0.3, call_frequency="per_request",
        modules_involved=["a", "b", "c"], estimated_effort="medium",
    )
    defaults.update(overrides)
    return _make_candidate(**defaults)


def _make_debt(**overrides) -> CandidatePathway:
    defaults = dict(
        candidate_type=CandidateType.PROHIBITED_CONNECTION,
        description="[KNOWN DEBT: x]", risk_level="medium", touches_protected=True,
    )
    defaults.update(overrides)
    return _make_candidate(**defaults)


# --- Basic ---
def test_score_in_range():
    assert 0 <= score_candidates([_make_candidate()])[0].score <= 100

def test_low_conf_caps_priority():
    assert score_candidates([_make_candidate(confidence=0.3, raw_confidence=0.3)])[0].priority == "low"

def test_prohibited_immediate():
    r = score_candidates([_make_candidate(candidate_type=CandidateType.PROHIBITED_CONNECTION, risk_level="critical", touches_protected=True)])[0]
    assert r.review_bucket == "immediate"

def test_known_debt_bucket():
    r = score_candidates([_make_debt()])[0]
    assert r.governance_status == "KNOWN_DEBT" and r.review_bucket == "known_debt"


# --- Watchlist ---
def test_watchlist_bucket():
    assert score_candidates([_make_watchlist()])[0].review_bucket == "watchlist"

def test_weak_stays_ignored():
    c = _make_candidate(candidate_type=CandidateType.LONG_PATH, confidence=0.3, raw_confidence=0.3, call_frequency="rare", modules_involved=["a", "b"], estimated_effort="large")
    assert score_candidates([c])[0].review_bucket == "ignore"


# --- Fingerprint ---
def test_fingerprint_deterministic():
    assert compute_fingerprint(_make_candidate(candidate_type=CandidateType.LONG_PATH, modules_involved=["a", "b"])) == \
           compute_fingerprint(_make_candidate(candidate_type=CandidateType.LONG_PATH, modules_involved=["a", "b"]))

def test_fingerprint_order_independent():
    assert compute_fingerprint(_make_candidate(modules_involved=["a", "b", "c"])) == \
           compute_fingerprint(_make_candidate(modules_involved=["c", "a", "b"]))


# --- Watchlist aging ---
def test_age_increments():
    c = _make_watchlist()
    fp = compute_fingerprint(c)
    assert score_candidates([c], previous_watchlist={fp: 1})[0].watchlist_age == 2

def test_new_watchlist_age_1():
    assert score_candidates([_make_watchlist()])[0].watchlist_age == 1


# --- Severity ---
def test_severity_increases_with_age():
    c = _make_watchlist()
    s1, _ = compute_watchlist_severity(50, 1, c)
    s2, _ = compute_watchlist_severity(50, 3, c)
    assert s2 > s1

def test_protected_escalates_faster():
    s_safe, _ = compute_watchlist_severity(50, 2, _make_watchlist(touches_protected=False))
    s_prot, _ = compute_watchlist_severity(50, 2, _make_watchlist(touches_protected=True))
    assert s_prot > s_safe

def test_drift_increases_severity():
    c = _make_watchlist(modules_involved=["a", "b", "c"])
    s_no, _ = compute_watchlist_severity(50, 2, c)
    s_yes, r = compute_watchlist_severity(50, 2, c, {"b": ModuleDrift("b", 3, 7, 2, 2, "notable_drift")})
    assert s_yes > s_no and "module_drift" in r

def test_escalation_threshold():
    c = _make_watchlist(touches_protected=True, risk_level="medium")
    fp = compute_fingerprint(c)
    r = score_candidates([c], previous_watchlist={fp: 4})[0]
    assert r.escalated_watchlist and r.watchlist_escalation_reason

def test_low_severity_not_escalated():
    assert not score_candidates([_make_watchlist()])[0].escalated_watchlist


# --- Debt lifecycle ---
def test_debt_age_increments():
    c = _make_debt()
    fp = compute_fingerprint(c)
    r = score_candidates([c], previous_debt={fp: 3})[0]
    assert r.debt_age == 4 and r.debt_status == "active"

def test_debt_review_due():
    c = _make_debt()
    fp = compute_fingerprint(c)
    r = score_candidates([c], previous_debt={fp: 4})[0]
    assert r.debt_age == 5 and r.debt_status == "review_due"


# --- Review queue ---
def test_escalated_enters_review_queue():
    c = _make_watchlist(touches_protected=True, risk_level="medium")
    fp = compute_fingerprint(c)
    r = score_candidates([c], previous_watchlist={fp: 4})[0]
    assert r.in_review_queue and r.operator_status == "unreviewed"

def test_review_due_debt_enters_queue():
    c = _make_debt()
    fp = compute_fingerprint(c)
    r = score_candidates([c], previous_debt={fp: 4})[0]
    assert r.in_review_queue and r.operator_status == "unreviewed"

def test_non_escalated_not_in_queue():
    r = score_candidates([_make_watchlist()])[0]
    assert not r.in_review_queue

def test_operator_status_persists():
    c = _make_watchlist(touches_protected=True, risk_level="medium")
    fp = compute_fingerprint(c)
    prev_rq = {fp: {"operator_status": "monitor", "operator_note": "watching this"}}
    r = score_candidates([c], previous_watchlist={fp: 4}, previous_review_queue=prev_rq)[0]
    assert r.operator_status == "monitor"
    assert r.operator_note == "watching this"

def test_why_now_present():
    c = _make_watchlist(touches_protected=True, risk_level="medium")
    fp = compute_fingerprint(c)
    r = score_candidates([c], previous_watchlist={fp: 4})[0]
    assert r.why_now != ""
    assert "persistent" in r.why_now or "touches protected" in r.why_now

def test_intervention_hint_present():
    c = _make_watchlist(touches_protected=True, risk_level="medium")
    fp = compute_fingerprint(c)
    r = score_candidates([c], previous_watchlist={fp: 4})[0]
    assert r.intervention_hint != ""

def test_debt_hint_present():
    c = _make_debt()
    fp = compute_fingerprint(c)
    r = score_candidates([c], previous_debt={fp: 4})[0]
    assert "service-layer" in r.intervention_hint.lower() or "review" in r.intervention_hint.lower()


# --- Score transparency ---
def test_breakdown_transparency():
    bd = score_candidates([_make_candidate()])[0].score_breakdown
    assert {"raw_confidence", "orchestrator_penalty", "final_confidence", "raw_score", "final_score"}.issubset(bd.keys())
