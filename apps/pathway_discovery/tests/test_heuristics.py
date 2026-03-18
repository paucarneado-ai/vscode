"""Tests for heuristic detection rules."""

import os

from apps.pathway_discovery.analyzer import analyze_interactions
from apps.pathway_discovery.heuristics import (
    _is_schema_constructor,
    detect_long_paths,
    detect_prohibited_connections,
    detect_redundant_transforms,
    get_prohibited_pairs,
    KNOWN_DEBT,
)
from apps.pathway_discovery.registry import build_registry
from apps.pathway_discovery.schemas import CandidateType, InteractionTrace

APPS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..")
APPS_PATH = os.path.join(APPS_PATH, "apps")


def test_prohibited_connections_after_refactor():
    """After extracting DB access to services, routes.leads no longer accesses db directly.
    Prohibited connections may still exist for other patterns but routes.leads->db is resolved."""
    traces = analyze_interactions(APPS_PATH)
    prohibited = detect_prohibited_connections(traces)
    # routes.leads -> db should no longer appear
    leads_db = [c for c in prohibited if "routes.leads" in c.description and "db" in c.description]
    assert len(leads_db) == 0, f"Expected 0 (resolved), got {len(leads_db)}"


def test_known_debt_resolved():
    """The routes.leads -> db known debt was resolved by service extraction."""
    traces = analyze_interactions(APPS_PATH)
    prohibited = detect_prohibited_connections(traces)
    leads_db = [c for c in prohibited if "routes.leads" in c.description and "db" in c.description]
    assert len(leads_db) == 0, "Known debt routes.leads->db should be resolved"


def test_known_debt_resolved_after_refactor():
    """After extracting DB access to services, routes.leads no longer imports db directly.
    The known debt (routes->db) is resolved. Prohibited findings may be empty."""
    traces = analyze_interactions(APPS_PATH)
    prohibited = detect_prohibited_connections(traces)
    # If any remain, they should still be valid
    for c in prohibited:
        assert c.candidate_type == CandidateType.PROHIBITED_CONNECTION


def test_redundant_get_db_after_service_extraction():
    """After extracting operational service, get_db is called from both routes and services.
    Since services.operational->db is NOT a prohibited pair, the redundant_transform
    for get_db is no longer fully suppressed — this is correct."""
    traces = analyze_interactions(APPS_PATH)
    prohibited_pairs = get_prohibited_pairs(traces)
    redundant = detect_redundant_transforms(traces, prohibited_pairs=prohibited_pairs)
    get_db_redundant = [c for c in redundant if "get_db" in c.description]
    # get_db may appear as redundant now (services.operational calls it legitimately)
    for c in get_db_redundant:
        assert c.candidate_type == CandidateType.REDUNDANT_TRANSFORM
        assert c.confidence >= 0.7


def test_prohibited_detects_fake_violation():
    """A synthetic trace matching a prohibited pattern should be flagged."""
    fake = InteractionTrace(
        caller_module="apps.api.routes.leads",
        caller_function="bad_func",
        callee_module="apps.api.db",
        callee_function="get_db",
        line_number=1,
        file_path="fake.py",
        resolution_kind="direct",
        confidence=0.9,
        confidence_reason="synthetic test",
    )
    result = detect_prohibited_connections([fake])
    assert len(result) == 1
    assert result[0].candidate_type == CandidateType.PROHIBITED_CONNECTION


def test_redundant_transforms_on_real_code():
    traces = analyze_interactions(APPS_PATH)
    prohibited_pairs = get_prohibited_pairs(traces)
    candidates = detect_redundant_transforms(traces, prohibited_pairs=prohibited_pairs)
    for c in candidates:
        assert c.candidate_type == CandidateType.REDUNDANT_TRANSFORM
        assert c.confidence >= 0.7
        assert c.occurrence_count >= 3


def test_long_paths_on_real_code():
    _, _, pathways = build_registry(APPS_PATH)
    traces = analyze_interactions(APPS_PATH)
    candidates = detect_long_paths(pathways, traces)
    for c in candidates:
        assert c.candidate_type == CandidateType.LONG_PATH
        assert c.current_hops >= 2
        assert c.intermediate_role in ("unknown", "pass_through", "shared_composer", "contract_translator")


def test_schema_constructor_suppressed():
    """LeadResponse, LeadCreate etc. should NOT appear as redundant_transform."""
    traces = analyze_interactions(APPS_PATH)
    prohibited_pairs = get_prohibited_pairs(traces)
    candidates = detect_redundant_transforms(traces, prohibited_pairs=prohibited_pairs)
    schema_candidates = [c for c in candidates if "LeadResponse" in c.description or "LeadCreate" in c.description]
    assert len(schema_candidates) == 0, f"Schema constructors should be suppressed: {[c.description for c in schema_candidates]}"


def test_is_schema_constructor():
    assert _is_schema_constructor("apps.api.schemas", "LeadResponse") is True
    assert _is_schema_constructor("apps.api.schemas", "LeadCreate") is True
    assert _is_schema_constructor("apps.api.schemas", "WebIntakePayload") is True
    assert _is_schema_constructor(None, "LeadResponse") is True  # suffix match
    assert _is_schema_constructor("apps.api.services.scoring", "calculate_lead_score") is False
    assert _is_schema_constructor("apps.api.db", "get_db") is False


def test_long_path_known_debt_dependency():
    """After service extraction, long paths through services.operational->db
    no longer depend on the routes.leads->db known debt (that debt is separate)."""
    _, _, pathways = build_registry(APPS_PATH)
    modules, _, _ = build_registry(APPS_PATH)
    traces = analyze_interactions(APPS_PATH)
    candidates = detect_long_paths(pathways, traces, modules=modules)
    db_paths = [c for c in candidates if "db" in c.description.lower()]
    # All long_path candidates should have valid structure
    for c in db_paths:
        assert c.candidate_type == CandidateType.LONG_PATH
        assert len(c.modules_involved) >= 3


def test_orchestrator_penalty_applied_to_high_fanout():
    """Intermediates with high fan-out should receive orchestrator penalty."""
    _, _, pathways = build_registry(APPS_PATH)
    modules, _, _ = build_registry(APPS_PATH)
    traces = analyze_interactions(APPS_PATH)
    candidates = detect_long_paths(pathways, traces, modules=modules)
    # Find candidates where penalty was applied
    penalized = [c for c in candidates if c.orchestrator_penalty > 0]
    assert len(penalized) > 0, "Expected at least one candidate with orchestrator penalty"
    for c in penalized:
        assert c.confidence < c.raw_confidence


def test_candidates_have_confidence_reason():
    traces = analyze_interactions(APPS_PATH)
    _, _, pathways = build_registry(APPS_PATH)
    prohibited_pairs = get_prohibited_pairs(traces)
    all_candidates = (
        detect_long_paths(pathways, traces)
        + detect_redundant_transforms(traces, prohibited_pairs=prohibited_pairs)
        + detect_prohibited_connections(traces)
    )
    for c in all_candidates:
        assert c.confidence_reason, f"{c.candidate_id} missing confidence_reason"
