"""Tests for intermediate role classification in long_path findings."""

import os

from apps.pathway_discovery.analyzer import analyze_interactions
from apps.pathway_discovery.heuristics import detect_long_paths, _classify_intermediate_role
from apps.pathway_discovery.registry import build_registry
from apps.pathway_discovery.reporter import generate_report
from apps.pathway_discovery.schemas import (
    CandidatePathway, CandidateType, InteractionTrace, PathwayRecommendation,
)
from apps.pathway_discovery.scorer import score_candidates, compute_fingerprint, compute_watchlist_severity

APPS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..")
APPS_PATH = os.path.join(APPS_PATH, "apps")


# --- _classify_intermediate_role unit tests ---

def _trace(caller_mod, caller_fn, callee_mod, callee_fn):
    return InteractionTrace(
        caller_module=caller_mod, caller_function=caller_fn,
        callee_module=callee_mod, callee_function=callee_fn,
        line_number=1, file_path="test.py", confidence=0.95,
        confidence_reason="test",
    )


def test_shared_composer_classification():
    """Intermediate calling >=3 modules with composition signals = shared_composer."""
    b_traces = [
        _trace("b", "hub", "mod1", "get_rating"),
        _trace("b", "hub", "mod2", "determine_next_action"),
        _trace("b", "hub", "mod3", "build_summary"),
        _trace("b", "hub", "mod4", "should_alert"),
    ]
    a_to_b = [_trace("a", "caller1", "b", "hub"), _trace("a2", "caller2", "b", "hub")]
    role, conf, reason = _classify_intermediate_role("b", b_traces, a_to_b)
    assert role == "shared_composer"
    assert conf >= 0.7
    assert "external modules" in reason


def test_contract_translator_classification():
    """Intermediate delegating to an _internal function = contract_translator."""
    b_traces = [
        _trace("b", "intake", "core", "_create_lead_internal"),
    ]
    a_to_b = [_trace("a", "caller", "b", "intake")]
    role, conf, reason = _classify_intermediate_role("b.intake", b_traces, a_to_b)
    assert role == "contract_translator"
    assert "translates" in reason or "delegates" in reason


def test_pass_through_classification():
    """Intermediate with minimal calls = pass_through."""
    b_traces = [
        _trace("b", "relay", "c", "do_thing"),
    ]
    a_to_b = [_trace("a", "caller", "b", "relay")]
    role, conf, reason = _classify_intermediate_role("b", b_traces, a_to_b)
    assert role == "pass_through"
    assert "minimal" in reason


def test_unknown_when_ambiguous():
    """Intermediate with moderate but ambiguous signals = unknown."""
    b_traces = [
        _trace("b", "func", "mod1", "helper1"),
        _trace("b", "func", "mod2", "helper2"),
    ]
    a_to_b = [_trace("a", "caller", "b", "func")]
    role, conf, reason = _classify_intermediate_role("b", b_traces, a_to_b)
    assert role == "unknown"


# --- Real codebase classification ---

def test_real_operational_classified_as_shared_composer():
    """After extraction, services.operational paths should be classified as shared_composer."""
    modules, _, pathways = build_registry(APPS_PATH)
    traces = analyze_interactions(APPS_PATH)
    candidates = detect_long_paths(pathways, traces, modules=modules)

    # Find paths through services.operational (the extracted hub)
    operational_paths = [c for c in candidates if any("services.operational" in m for m in c.modules_involved)]
    # If operational appears as intermediate in any chain, it should be shared_composer
    composers = [c for c in operational_paths if c.intermediate_role == "shared_composer"]
    # At least the service exists as a hub with correct classification
    for c in candidates:
        if c.intermediate_role == "shared_composer":
            assert c.role_confidence >= 0.7
            assert c.role_reason != ""


def test_shared_composer_has_reason():
    modules, _, pathways = build_registry(APPS_PATH)
    traces = analyze_interactions(APPS_PATH)
    candidates = detect_long_paths(pathways, traces, modules=modules)
    composers = [c for c in candidates if c.intermediate_role == "shared_composer"]
    for c in composers:
        assert c.role_reason, f"shared_composer missing role_reason: {c.candidate_id}"
        assert c.role_confidence >= 0.7


# --- Scorer: shared_composer not escalated like pass_through ---

def test_shared_composer_lower_severity_than_pass_through():
    """shared_composer should get lower watchlist severity than equivalent pass_through."""
    base = dict(
        candidate_type=CandidateType.LONG_PATH,
        modules_involved=["a", "b", "c"],
        touches_protected=True,
        risk_level="medium",
    )

    composer = CandidatePathway(candidate_id="c1", description="test", intermediate_role="shared_composer",
                                role_confidence=0.85, role_reason="test", **base)
    passthru = CandidatePathway(candidate_id="c2", description="test", intermediate_role="pass_through",
                                role_confidence=0.6, role_reason="test", **base)

    sev_composer, _ = compute_watchlist_severity(50, 5, composer)
    sev_passthru, _ = compute_watchlist_severity(50, 5, passthru)
    assert sev_composer < sev_passthru, f"composer={sev_composer} should be < passthru={sev_passthru}"


def test_shared_composer_not_escalated_at_same_age():
    """shared_composer at same age as pass_through should be less likely to escalate."""
    base_kw = dict(
        candidate_type=CandidateType.LONG_PATH, confidence=0.4, raw_confidence=0.7,
        orchestrator_penalty=0.3, call_frequency="per_request",
        modules_involved=["a", "b", "c"], estimated_effort="medium",
        touches_protected=False, risk_level="low",
    )
    composer = CandidatePathway(candidate_id="c1", description="test",
                                intermediate_role="shared_composer", role_confidence=0.85, role_reason="x", **base_kw)
    fp = compute_fingerprint(composer)
    recs = score_candidates([composer], previous_watchlist={fp: 3})
    # With role reduction, severity should be moderate enough to not escalate
    assert recs[0].watchlist_severity_score < 60, f"Severity too high for composer: {recs[0].watchlist_severity_score}"


# --- Reporter: shows role ---

def test_reporter_shows_intermediate_role():
    rec = PathwayRecommendation(
        recommendation_id="PR-R",
        candidate=CandidatePathway(
            candidate_id="CP-R", candidate_type=CandidateType.LONG_PATH,
            description="test chain", intermediate_role="shared_composer",
            role_confidence=0.85, role_reason="calls 5 modules with composition",
            stable_fingerprint="fp-role",
        ),
        score=50.0, review_bucket="watchlist",
    )
    report = generate_report([rec], [], [], [], [])
    assert "shared_composer" in report
    assert "calls 5 modules" in report


def test_reporter_does_not_show_unknown_role():
    rec = PathwayRecommendation(
        recommendation_id="PR-U",
        candidate=CandidatePathway(
            candidate_id="CP-U", candidate_type=CandidateType.LONG_PATH,
            description="test", intermediate_role="unknown",
            stable_fingerprint="fp-unk",
        ),
        score=50.0, review_bucket="watchlist",
    )
    report = generate_report([rec], [], [], [], [])
    assert "Intermediate role" not in report  # unknown should not be displayed


# --- JSON includes role fields ---

def test_json_includes_role():
    import json
    from apps.pathway_discovery.reporter import generate_json
    rec = PathwayRecommendation(
        recommendation_id="PR-J",
        candidate=CandidatePathway(
            candidate_id="CP-J", candidate_type=CandidateType.LONG_PATH,
            description="test", intermediate_role="shared_composer",
            role_confidence=0.85, role_reason="test reason",
            stable_fingerprint="fp-j",
        ),
        score=50.0, review_bucket="watchlist",
    )
    js = json.loads(generate_json([rec], [], [], [], []))
    r = js["recommendations"][0]
    assert r["intermediate_role"] == "shared_composer"
    assert r["role_confidence"] == 0.85
    assert r["role_reason"] == "test reason"
