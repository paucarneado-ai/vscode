"""Tests for scripts/cartographer.py — uses isolated fixtures, not the real repo."""

import json
import os
import subprocess
import sys
import tempfile

import pytest

# Add project root to path so we can import the cartographer functions
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.cartographer import (
    compute_temporal_diff,
    detect_drift,
    reconcile,
    write_drift_report,
    write_json,
    write_markdown,
)


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════

AUDIT_FIXTURE = """# Built State Audit

## 1. Lead Engine — DONE

**Archivos**: apps/api/services/intake.py, scoring.py, actions.py

Some description here.

## 2. Admin Panel — MOSTLY_DONE

**Archivo**: `tools/admin.html`

## 3. Landing vendedores — DONE

**Archivo**: `static/site/es/vender-mi-barco/index.html`

## 4. Notificaciones — PLANNED

No code yet.

## 5. Old Script — DEPRECATED

**Archivo**: `scripts/old.py`
"""

PLAN_FIXTURE = """# Master Plan

## Structure

| Módulo | Función | Fase |
|---|---|---|
| **Lead Engine** | Motor de leads | MVP |
| **Admin de barcos** | Panel interno | MVP |
| **Landing de compra** | Página compradores | Posterior |
| **Notificaciones** | WhatsApp/email | Siguiente |
"""


@pytest.fixture
def audit_content():
    return AUDIT_FIXTURE


@pytest.fixture
def plan_content():
    return PLAN_FIXTURE


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


# ═══════════════════════════════════════════════════════════════════
# Audit seed parsing
# ═══════════════════════════════════════════════════════════════════

def _parse_audit(content):
    """Inline parser matching cartographer's load_audit_seed logic."""
    import re
    AUDIT_STATUS_TAGS = {"DONE", "MOSTLY_DONE", "PARTIAL", "SCAFFOLD", "PLANNED", "DEPRECATED"}
    modules = []
    for m in re.finditer(r"^## \d+\.\s+(.+?)\s*—\s*(\w+)", content, re.MULTILINE):
        name = m.group(1).strip()
        status = m.group(2).strip()
        if status not in AUDIT_STATUS_TAGS:
            status = "UNKNOWN"
        start = m.end()
        next_section = re.search(r"^## ", content[start:], re.MULTILINE)
        body = content[start:start + next_section.start()] if next_section else content[start:]
        files = re.findall(r"`([a-zA-Z0-9_/.\-]+\.(?:py|html|js|json|md|sh))`", body)
        for archivos_match in re.finditer(r"\*\*Archivos?\*\*:\s*(.+)", body):
            line = archivos_match.group(1)
            for token in re.split(r"[,;]", line):
                token = token.strip().split("(")[0].strip()
                if re.match(r"[a-zA-Z0-9_/.\-]+\.(?:py|html|js|json|md|sh)$", token):
                    files.append(token)
        for archivo_match in re.finditer(r"\*\*Archivo\*\*:\s*`?([a-zA-Z0-9_/.\-]+\.(?:py|html|js|json|md|sh))`?", body):
            files.append(archivo_match.group(1))
        modules.append({"name": name, "status": status, "files_mentioned": files,
                        "provenance": "inherited_from_seed_map", "seed_source": "audit"})
    return modules


def test_audit_parses_all_modules(audit_content):
    modules = _parse_audit(audit_content)
    assert len(modules) == 5
    names = [m["name"] for m in modules]
    assert "Lead Engine" in names
    assert "Admin Panel" in names
    assert "Notificaciones" in names


def test_audit_extracts_status_tags(audit_content):
    modules = _parse_audit(audit_content)
    status_map = {m["name"]: m["status"] for m in modules}
    assert status_map["Lead Engine"] == "DONE"
    assert status_map["Admin Panel"] == "MOSTLY_DONE"
    assert status_map["Notificaciones"] == "PLANNED"
    assert status_map["Old Script"] == "DEPRECATED"


def test_audit_extracts_archivos_line(audit_content):
    modules = _parse_audit(audit_content)
    lead = next(m for m in modules if m["name"] == "Lead Engine")
    assert "apps/api/services/intake.py" in lead["files_mentioned"]
    assert "scoring.py" in lead["files_mentioned"]
    assert "actions.py" in lead["files_mentioned"]


def test_audit_extracts_archivo_singular_backtick(audit_content):
    modules = _parse_audit(audit_content)
    admin = next(m for m in modules if m["name"] == "Admin Panel")
    assert "tools/admin.html" in admin["files_mentioned"]


def test_audit_planned_has_no_files(audit_content):
    modules = _parse_audit(audit_content)
    notif = next(m for m in modules if m["name"] == "Notificaciones")
    assert notif["files_mentioned"] == []


# ═══════════════════════════════════════════════════════════════════
# Master plan parsing
# ═══════════════════════════════════════════════════════════════════

def _parse_plan(content):
    """Inline parser matching cartographer's load_master_plan_seed logic."""
    import re
    blocks = []
    for m in re.finditer(r"\|\s*\*?\*?([^|*]+?)\*?\*?\s*\|\s*([^|]+)\|\s*([^|]+)\|", content):
        name = m.group(1).strip()
        description = m.group(2).strip()
        phase = m.group(3).strip()
        if not name or name.startswith("---") or name == "Módulo":
            continue
        blocks.append({"name": name, "description": description, "phase": phase,
                       "provenance": "inherited_from_seed_map", "seed_source": "master_plan"})
    return blocks


def test_plan_parses_blocks(plan_content):
    blocks = _parse_plan(plan_content)
    assert len(blocks) == 4
    names = [b["name"] for b in blocks]
    assert "Lead Engine" in names
    assert "Landing de compra" in names


def test_plan_extracts_phases(plan_content):
    blocks = _parse_plan(plan_content)
    phase_map = {b["name"]: b["phase"] for b in blocks}
    assert phase_map["Lead Engine"] == "MVP"
    assert phase_map["Landing de compra"] == "Posterior"
    assert phase_map["Notificaciones"] == "Siguiente"


def test_plan_skips_header_row(plan_content):
    blocks = _parse_plan(plan_content)
    names = [b["name"] for b in blocks]
    assert "Módulo" not in names


# ═══════════════════════════════════════════════════════════════════
# Basename matching in reconciliation
# ═══════════════════════════════════════════════════════════════════

def test_basename_matching_unique():
    """scoring.py should resolve to apps/api/services/scoring.py when unique."""
    project_map = {
        "python_packages": [
            {"type": "python_module", "file": "apps/api/services/scoring.py"},
            {"type": "python_module", "file": "apps/api/services/intake.py"},
        ],
    }
    audit_modules = [{
        "name": "Test Module", "status": "DONE",
        "files_mentioned": ["scoring.py"],
        "provenance": "inherited_from_seed_map", "seed_source": "audit",
    }]
    result = reconcile(project_map, audit_modules, [])
    mod = result[0]
    assert mod["validation"] == "confirmed"
    assert len(mod["files_confirmed_in_code"]) == 1
    assert "scoring.py" in mod["files_confirmed_in_code"][0]
    assert "apps/api/services/scoring.py" in mod["files_confirmed_in_code"][0]


def test_basename_matching_ambiguous():
    """If basename has multiple matches, still confirms but flags ambiguity."""
    project_map = {
        "python_packages": [
            {"type": "python_module", "file": "apps/api/schemas.py"},
            {"type": "python_module", "file": "apps/pathway_discovery/schemas.py"},
        ],
    }
    audit_modules = [{
        "name": "Test", "status": "DONE",
        "files_mentioned": ["schemas.py"],
        "provenance": "inherited_from_seed_map", "seed_source": "audit",
    }]
    result = reconcile(project_map, audit_modules, [])
    mod = result[0]
    assert mod["validation"] == "confirmed"
    assert "ambiguous" in mod["files_confirmed_in_code"][0]


def test_basename_matching_no_match():
    """If basename doesn't exist anywhere, it's missing."""
    project_map = {"python_packages": []}
    audit_modules = [{
        "name": "Test", "status": "DONE",
        "files_mentioned": ["nonexistent.py"],
        "provenance": "inherited_from_seed_map", "seed_source": "audit",
    }]
    result = reconcile(project_map, audit_modules, [])
    mod = result[0]
    assert mod["validation"] == "needs_validation"
    assert "nonexistent.py" in mod["files_missing_from_code"]


def test_exact_path_takes_priority():
    """Full path match should work without needing basename fallback."""
    project_map = {
        "python_packages": [
            {"type": "python_module", "file": "apps/api/services/scoring.py"},
        ],
    }
    audit_modules = [{
        "name": "Test", "status": "DONE",
        "files_mentioned": ["apps/api/services/scoring.py"],
        "provenance": "inherited_from_seed_map", "seed_source": "audit",
    }]
    result = reconcile(project_map, audit_modules, [])
    mod = result[0]
    assert mod["validation"] == "confirmed"
    assert mod["files_confirmed_in_code"] == ["apps/api/services/scoring.py"]


# ═══════════════════════════════════════════════════════════════════
# Full reconciliation
# ═══════════════════════════════════════════════════════════════════

def test_reconcile_audit_and_plan_merge():
    """Plan blocks not in audit appear as needs_validation."""
    project_map = {"python_packages": []}
    audit_modules = [{
        "name": "Engine", "status": "DONE", "files_mentioned": [],
        "provenance": "inherited_from_seed_map", "seed_source": "audit",
    }]
    plan_blocks = [
        {"name": "Engine", "description": "core", "phase": "MVP",
         "provenance": "inherited_from_seed_map", "seed_source": "master_plan"},
        {"name": "Dashboard", "description": "metrics UI", "phase": "Posterior",
         "provenance": "inherited_from_seed_map", "seed_source": "master_plan"},
    ]
    result = reconcile(project_map, audit_modules, plan_blocks)
    assert len(result) == 2
    engine = next(r for r in result if r["module"] == "Engine")
    assert engine["plan_phase"] == "MVP"
    assert engine["audit_status"] == "DONE"
    dashboard = next(r for r in result if r["module"] == "Dashboard")
    assert dashboard["plan_phase"] == "Posterior"
    assert dashboard["audit_status"] is None
    assert dashboard["validation"] == "needs_validation"


# ═══════════════════════════════════════════════════════════════════
# Temporal diff
# ═══════════════════════════════════════════════════════════════════

def test_temporal_diff_no_previous():
    result = compute_temporal_diff({}, None)
    assert result["available"] is False


def test_temporal_diff_detects_added():
    prev = {"files": [{"file": "a.py"}, {"file": "b.py"}]}
    curr = {"files": [{"file": "a.py"}, {"file": "b.py"}, {"file": "c.py"}]}
    result = compute_temporal_diff(curr, prev)
    assert result["available"] is True
    assert "c.py" in result["files_added"]
    assert result["files_removed"] == []


def test_temporal_diff_detects_removed():
    prev = {"files": [{"file": "a.py"}, {"file": "b.py"}]}
    curr = {"files": [{"file": "a.py"}]}
    result = compute_temporal_diff(curr, prev)
    assert "b.py" in result["files_removed"]


def test_temporal_diff_detects_category_changes():
    prev = {"scripts": [{"file": "a.py"}, {"file": "b.py"}], "docs": [{"file": "x.md"}]}
    curr = {"scripts": [{"file": "a.py"}], "docs": [{"file": "x.md"}, {"file": "y.md"}]}
    result = compute_temporal_diff(curr, prev)
    assert "scripts" in result["category_changes"]
    assert result["category_changes"]["scripts"]["delta"] == -1
    assert result["category_changes"]["docs"]["delta"] == 1


def test_temporal_diff_no_changes():
    data = {"files": [{"file": "a.py"}]}
    result = compute_temporal_diff(data, data)
    assert result["available"] is True
    assert result["files_added"] == []
    assert result["files_removed"] == []


# ═══════════════════════════════════════════════════════════════════
# Output files
# ═══════════════════════════════════════════════════════════════════

def test_write_json_deterministic(tmp_dir):
    data = {"version": 1, "items": [{"file": "b.py"}, {"file": "a.py"}]}
    path1 = os.path.join(tmp_dir, "map1.json")
    path2 = os.path.join(tmp_dir, "map2.json")
    write_json(data, path1)
    write_json(data, path2)
    with open(path1) as f:
        content1 = f.read()
    with open(path2) as f:
        content2 = f.read()
    assert content1 == content2
    parsed = json.loads(content1)
    assert parsed["version"] == 1


def test_write_markdown_has_sections(tmp_dir):
    project_map = {
        "generated_at": "2026-01-01T00:00:00Z",
        "html_pages": [{"type": "html_page", "file": "index.html", "public_url": "/",
                        "title": "Home", "generated": False, "provenance": "detected_from_code"}],
        "api_routes": [{"type": "api_route", "method": "GET", "path": "/health",
                        "auth_required": False, "source_file": "health.py", "provenance": "detected_from_code"}],
        "python_packages": [], "scripts": [], "docs": [], "tools": [],
        "data_files": [], "static_assets": [], "tests": [], "pathway_tests": [], "configs": [],
    }
    reconciled = [{"module": "Test", "audit_status": "DONE", "plan_phase": "MVP",
                   "files_confirmed_in_code": ["x.py"], "files_missing_from_code": [],
                   "validation": "confirmed"}]
    path = os.path.join(tmp_dir, "map.md")
    write_markdown(project_map, reconciled, path)
    with open(path) as f:
        content = f.read()
    assert "## Module Status" in content
    assert "## HTML Pages" in content
    assert "## API Routes" in content
    assert "/health" in content
    assert "Home" in content


def test_write_drift_report_temporal_section(tmp_dir):
    drift = []
    reconciled = []
    temporal = {"available": True, "previous_generated_at": "2026-01-01",
                "files_added": ["new.py"], "files_removed": [], "category_changes": {}}
    path = os.path.join(tmp_dir, "drift.md")
    write_drift_report(drift, reconciled, temporal, path)
    with open(path) as f:
        content = f.read()
    assert "Changes since last scan" in content
    assert "new.py" in content


def test_write_drift_report_no_previous(tmp_dir):
    path = os.path.join(tmp_dir, "drift.md")
    write_drift_report([], [], {"available": False}, path)
    with open(path) as f:
        content = f.read()
    assert "First run" in content


# ═══════════════════════════════════════════════════════════════════
# Output determinism
# ═══════════════════════════════════════════════════════════════════

def test_markdown_output_stable_across_runs(tmp_dir):
    """Same input should produce byte-identical markdown."""
    project_map = {
        "generated_at": "FIXED_TIMESTAMP",
        "html_pages": [
            {"type": "html_page", "file": "b.html", "public_url": "/b/", "title": "B", "generated": False, "provenance": "detected_from_code"},
            {"type": "html_page", "file": "a.html", "public_url": "/a/", "title": "A", "generated": True, "provenance": "detected_from_code"},
        ],
        "api_routes": [
            {"type": "api_route", "method": "POST", "path": "/z", "auth_required": True, "source_file": "z.py", "provenance": "detected_from_code"},
            {"type": "api_route", "method": "GET", "path": "/a", "auth_required": False, "source_file": "a.py", "provenance": "detected_from_code"},
        ],
        "python_packages": [], "scripts": [], "docs": [], "tools": [],
        "data_files": [], "static_assets": [], "tests": [], "pathway_tests": [], "configs": [],
    }
    reconciled = []
    p1 = os.path.join(tmp_dir, "run1.md")
    p2 = os.path.join(tmp_dir, "run2.md")
    write_markdown(project_map, reconciled, p1)
    write_markdown(project_map, reconciled, p2)
    with open(p1) as f:
        c1 = f.read()
    with open(p2) as f:
        c2 = f.read()
    assert c1 == c2
    # Verify sorting: /a/ before /b/ in HTML pages section
    lines = c1.split("\n")
    url_lines = [l for l in lines if l.startswith("| `/")]
    a_idx = next(i for i, l in enumerate(url_lines) if "/a/" in l)
    b_idx = next(i for i, l in enumerate(url_lines) if "/b/" in l)
    assert a_idx < b_idx, "HTML pages should be sorted by URL"


# ═══════════════════════════════════════════════════════════════════
# Group documentation rules (drift noise reduction)
# ═══════════════════════════════════════════════════════════════════

def test_group_documented_pages_not_flagged():
    """Pages covered by GROUP_DOCUMENTED_PATTERNS should not appear as drift."""
    from scripts.cartographer import detect_drift

    project_map = {
        "html_pages": [
            {"type": "html_page", "file": "static/site/es/barcos/test/index.html",
             "public_url": "/es/barcos/test/", "provenance": "detected_from_code"},
            {"type": "html_page", "file": "static/site/es/aviso-legal/index.html",
             "public_url": "/es/aviso-legal/", "provenance": "detected_from_code"},
            {"type": "html_page", "file": "static/site/en/privacy-policy/index.html",
             "public_url": "/en/privacy-policy/", "provenance": "detected_from_code"},
            {"type": "html_page", "file": "static/site/es/yates-en-venta/index.html",
             "public_url": "/es/yates-en-venta/", "provenance": "detected_from_code"},
        ],
        "api_routes": [],
        "python_packages": [],
    }
    # detect_drift reads the real audit file — these patterns should be suppressed
    drift = detect_drift(project_map, [])
    urls_flagged = [d["issue"] for d in drift if "HTML page" in d["issue"]]
    assert not any("/es/barcos/" in u for u in urls_flagged), "boat detail pages should be group-suppressed"
    assert not any("/es/aviso-legal/" in u for u in urls_flagged), "legal pages should be group-suppressed"
    assert not any("/en/privacy-policy/" in u for u in urls_flagged), "EN legal should be group-suppressed"
    assert not any("/es/yates-en-venta/" in u for u in urls_flagged), "catalog should be group-suppressed"


def test_group_documented_admin_routes_not_flagged():
    """Admin routes under /internal/admin/ should not appear as drift."""
    from scripts.cartographer import detect_drift

    project_map = {
        "html_pages": [],
        "api_routes": [
            {"type": "api_route", "method": "GET", "path": "/internal/admin/boats",
             "auth_required": True, "source_file": "admin.py", "provenance": "detected_from_code"},
            {"type": "api_route", "method": "PUT", "path": "/internal/admin/boats/{slug}/data",
             "auth_required": True, "source_file": "admin.py", "provenance": "detected_from_code"},
        ],
        "python_packages": [],
    }
    drift = detect_drift(project_map, [])
    route_issues = [d for d in drift if "API route" in d["issue"]]
    assert len(route_issues) == 0, "admin routes should be group-suppressed"


def test_ungrouped_page_still_flagged():
    """A truly undocumented page should still appear as drift."""
    from scripts.cartographer import detect_drift

    project_map = {
        "html_pages": [
            {"type": "html_page", "file": "static/site/es/nueva-seccion/index.html",
             "public_url": "/es/nueva-seccion/", "provenance": "detected_from_code"},
        ],
        "api_routes": [],
        "python_packages": [],
    }
    drift = detect_drift(project_map, [])
    urls_flagged = [d["issue"] for d in drift if "HTML page" in d["issue"]]
    assert any("/es/nueva-seccion/" in u for u in urls_flagged), "truly new page should be flagged"


# ═══════════════════════════════════════════════════════════════════
# Smoke test — runs cartographer against the real repo
# ═══════════════════════════════════════════════════════════════════

def test_cartographer_smoke():
    """Run cartographer end-to-end on the real repo. Verify outputs are valid."""
    project_root = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
    script = os.path.join(project_root, "scripts", "cartographer.py")

    # Run cartographer
    result = subprocess.run(
        [sys.executable, script],
        capture_output=True, text=True, timeout=30,
        cwd=project_root,
    )
    assert result.returncode == 0, f"Cartographer failed:\n{result.stderr}"

    # 1. project_map.json exists and parses
    json_path = os.path.join(project_root, "reports", "project_map.json")
    assert os.path.isfile(json_path)
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    assert "generated_at" in data
    assert "version" in data
    assert isinstance(data.get("html_pages"), list)
    assert isinstance(data.get("api_routes"), list)
    assert isinstance(data.get("python_packages"), list)
    assert isinstance(data.get("reconciled_modules"), list)
    assert len(data["html_pages"]) > 0
    assert len(data["api_routes"]) > 0

    # 2. project_map.md exists and has key sections
    md_path = os.path.join(project_root, "docs", "project_map.md")
    assert os.path.isfile(md_path)
    with open(md_path, encoding="utf-8") as f:
        md = f.read()
    for section in ["## Module Status", "## HTML Pages", "## API Routes",
                    "## Python Modules", "## Tests", "## Documentation"]:
        assert section in md, f"Missing section: {section}"

    # 3. drift report exists and has structure
    drift_path = os.path.join(project_root, "reports", "project_drift_report.md")
    assert os.path.isfile(drift_path)
    with open(drift_path, encoding="utf-8") as f:
        drift = f.read()
    assert "# Project Drift Report" in drift
    assert "Changes since last scan" in drift

    # 4. Counts are sane (not zero, not absurd)
    assert len(data["html_pages"]) >= 1
    assert len(data["api_routes"]) >= 1
    assert len(data["python_packages"]) >= 1
    assert len(data["reconciled_modules"]) >= 10


def test_cartographer_idempotent():
    """Two consecutive runs produce identical outputs (except generated_at timestamps)."""
    project_root = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
    script = os.path.join(project_root, "scripts", "cartographer.py")

    json_path = os.path.join(project_root, "reports", "project_map.json")
    md_path = os.path.join(project_root, "docs", "project_map.md")
    drift_path = os.path.join(project_root, "reports", "project_drift_report.md")

    # Run 1
    r1 = subprocess.run([sys.executable, script], capture_output=True, text=True, timeout=30, cwd=project_root)
    assert r1.returncode == 0
    with open(json_path, encoding="utf-8") as f:
        json1 = json.load(f)
    with open(md_path, encoding="utf-8") as f:
        md1 = f.read()
    with open(drift_path, encoding="utf-8") as f:
        drift1 = f.read()

    # Run 2
    r2 = subprocess.run([sys.executable, script], capture_output=True, text=True, timeout=30, cwd=project_root)
    assert r2.returncode == 0
    with open(json_path, encoding="utf-8") as f:
        json2 = json.load(f)
    with open(md_path, encoding="utf-8") as f:
        md2 = f.read()
    with open(drift_path, encoding="utf-8") as f:
        drift2 = f.read()

    # Compare JSON: strip generated_at and temporal_diff timestamps before comparing
    def _strip_timestamps(d):
        d = dict(d)
        d.pop("generated_at", None)
        if "temporal_diff" in d:
            td = dict(d["temporal_diff"])
            td.pop("previous_generated_at", None)
            d["temporal_diff"] = td
        return d

    assert _strip_timestamps(json1) == _strip_timestamps(json2), "JSON output differs between runs"

    # Compare markdown: strip the Generated: line
    def _strip_generated_line(text):
        return "\n".join(l for l in text.split("\n") if not l.startswith("Generated:"))

    assert _strip_generated_line(md1) == _strip_generated_line(md2), "Markdown output differs between runs"

    # Compare drift: strip Generated: and timestamp in "Changes since" header
    def _strip_drift_timestamps(text):
        lines = []
        for l in text.split("\n"):
            if l.startswith("Generated:") or l.startswith("## Changes since last scan"):
                continue
            lines.append(l)
        return "\n".join(lines)

    assert _strip_drift_timestamps(drift1) == _strip_drift_timestamps(drift2), "Drift report differs between runs"
