"""Tests for the module registry builder."""

import os

from apps.pathway_discovery.registry import build_registry

APPS_ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..")
APPS_PATH = os.path.join(APPS_ROOT, "apps")


def test_build_registry_returns_modules():
    modules, functions, pathways = build_registry(APPS_PATH)
    assert len(modules) > 0
    ids = {m.module_id for m in modules}
    # Must find core modules
    assert any("routes.leads" in mid for mid in ids)
    assert any("services.scoring" in mid for mid in ids)
    assert any("schemas" in mid for mid in ids)


def test_build_registry_returns_functions():
    _, functions, _ = build_registry(APPS_PATH)
    assert len(functions) > 0
    func_names = {f.function_name for f in functions}
    assert "calculate_lead_score" in func_names
    assert "create_lead" in func_names


def test_build_registry_returns_pathways():
    _, _, pathways = build_registry(APPS_PATH)
    assert len(pathways) > 0
    # After refactor, intake service imports from scoring
    assert any(
        "scoring" in p.target_module and "intake" in p.source_module
        for p in pathways
    )


def test_protected_modules_flagged():
    modules, _, _ = build_registry(APPS_PATH)
    scoring = [m for m in modules if "scoring" in m.module_id]
    assert len(scoring) > 0
    assert scoring[0].protected is True

    db = [m for m in modules if m.module_id.endswith("db")]
    assert len(db) > 0
    assert db[0].protected is True


def test_module_kind_classification():
    modules, _, _ = build_registry(APPS_PATH)
    kinds = {m.module_id: m.module_kind for m in modules}
    assert any(k == "route" for k in kinds.values())
    assert any(k == "service" for k in kinds.values())
    assert any(k == "schema" for k in kinds.values())


def test_fan_in_fan_out_non_negative():
    modules, _, _ = build_registry(APPS_PATH)
    for m in modules:
        assert m.fan_in >= 0
        assert m.fan_out >= 0


def test_excludes_pathway_discovery():
    modules, _, _ = build_registry(APPS_PATH)
    assert not any("pathway_discovery" in m.module_id for m in modules)
