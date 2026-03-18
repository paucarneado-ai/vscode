"""Tests for the interaction analyzer."""

import os

from apps.pathway_discovery.analyzer import analyze_interactions

APPS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..")
APPS_PATH = os.path.join(APPS_PATH, "apps")


def test_analyze_returns_traces():
    traces = analyze_interactions(APPS_PATH)
    assert len(traces) > 0


def test_finds_scoring_call():
    traces = analyze_interactions(APPS_PATH)
    scoring_traces = [
        t for t in traces
        if t.callee_function == "calculate_lead_score" and t.callee_module
        and "scoring" in t.callee_module
    ]
    assert len(scoring_traces) >= 1
    assert scoring_traces[0].resolution_kind == "direct"
    assert scoring_traces[0].confidence >= 0.9


def test_direct_calls_have_high_confidence():
    traces = analyze_interactions(APPS_PATH)
    direct = [t for t in traces if t.resolution_kind == "direct"]
    assert len(direct) > 0
    for t in direct:
        assert t.confidence >= 0.9


def test_attribute_calls_have_medium_confidence():
    traces = analyze_interactions(APPS_PATH)
    attr = [t for t in traces if t.resolution_kind == "attribute"]
    # db.execute calls should show up as attribute
    if attr:
        for t in attr:
            assert 0.5 <= t.confidence <= 0.9


def test_no_builtin_traces():
    traces = analyze_interactions(APPS_PATH)
    builtins = {"print", "len", "str", "int", "dict", "list", "min", "max", "round"}
    for t in traces:
        assert t.callee_function not in builtins


def test_excludes_pathway_discovery():
    traces = analyze_interactions(APPS_PATH)
    assert not any("pathway_discovery" in t.caller_module for t in traces)
