"""Project Cartographer v2.1 — reconciles repo reality with seed maps.

Layers reconciled:
  A. docs/openclaw_built_state_audit.md  (seed: built state + status tags)
  B. docs/openclaw_master_plan.md        (seed: target state + phases)
  C. reports/project_map.json            (previous scan — used for temporal diff)
  D. Repo filesystem                     (ground truth)

Provenance categories:
  - detected_from_code: found by scanning actual files/code
  - inherited_from_seed_map: extracted from audit or master plan docs
  - inferred: derived from patterns (e.g., basename matching)

Validation states (on reconciled modules):
  - confirmed: audit files verified in code
  - needs_validation: audit references files not found in code (or plan block without audit entry)
  - no_files_to_check: audit section doesn't reference specific files

Outputs:
  - reports/project_map.json
  - docs/project_map.md
  - reports/project_drift_report.md

Usage: python scripts/cartographer.py
"""

import json
import os
import re
import sys
from datetime import datetime, timezone

PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))

IGNORE_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    ".mypy_cache", ".ruff_cache", ".pytest_cache", "_backup",
    ".claude", ".devcontainer",
}


# ═══════════════════════════════════════════════════════════════════
# Seed map parsers
# ═══════════════════════════════════════════════════════════════════

AUDIT_STATUS_TAGS = {"DONE", "MOSTLY_DONE", "PARTIAL", "SCAFFOLD", "PLANNED", "DEPRECATED"}


def load_audit_seed() -> list[dict]:
    """Parse openclaw_built_state_audit.md to extract module blocks with status tags."""
    path = os.path.join(PROJECT_ROOT, "docs", "openclaw_built_state_audit.md")
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as f:
        content = f.read()

    modules = []
    # Match headers like: ## 1. Lead Engine — DONE
    for m in re.finditer(r"^## \d+\.\s+(.+?)\s*—\s*(\w+)", content, re.MULTILINE):
        name = m.group(1).strip()
        status = m.group(2).strip()
        if status not in AUDIT_STATUS_TAGS:
            status = "UNKNOWN"
        # Extract the section body until next ## or end
        start = m.end()
        next_section = re.search(r"^## ", content[start:], re.MULTILINE)
        body = content[start:start + next_section.start()] if next_section else content[start:]
        # Extract file paths mentioned (both backtick-quoted and in **Archivos**: lines)
        files = re.findall(r"`([a-zA-Z0-9_/.\-]+\.(?:py|html|js|json|md|sh))`", body)
        # Also extract from **Archivos**: lines (comma-separated, may have parenthetical notes)
        for archivos_match in re.finditer(r"\*\*Archivos?\*\*:\s*(.+)", body):
            line = archivos_match.group(1)
            # Split by comma, extract file-like tokens
            for token in re.split(r"[,;]", line):
                token = token.strip().split("(")[0].strip()  # strip parenthetical
                if re.match(r"[a-zA-Z0-9_/.\-]+\.(?:py|html|js|json|md|sh)$", token):
                    files.append(token)
        # Also extract from **Archivo**: singular
        for archivo_match in re.finditer(r"\*\*Archivo\*\*:\s*`?([a-zA-Z0-9_/.\-]+\.(?:py|html|js|json|md|sh))`?", body):
            files.append(archivo_match.group(1))
        modules.append({
            "name": name,
            "status": status,
            "files_mentioned": files,
            "provenance": "inherited_from_seed_map",
            "seed_source": "audit",
        })
    return modules


def load_master_plan_seed() -> list[dict]:
    """Parse openclaw_master_plan.md to extract target blocks with phases."""
    path = os.path.join(PROJECT_ROOT, "docs", "openclaw_master_plan.md")
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as f:
        content = f.read()

    blocks = []
    # Match table rows like: | **Landing de captación** | ... | MVP (DONE) |
    for m in re.finditer(
        r"\|\s*\*?\*?([^|*]+?)\*?\*?\s*\|\s*([^|]+)\|\s*([^|]+)\|",
        content,
    ):
        name = m.group(1).strip()
        description = m.group(2).strip()
        phase = m.group(3).strip()
        if not name or name.startswith("---") or name == "Módulo":
            continue
        blocks.append({
            "name": name,
            "description": description,
            "phase": phase,
            "provenance": "inherited_from_seed_map",
            "seed_source": "master_plan",
        })
    return blocks


def load_previous_map() -> dict | None:
    """Load the previous project_map.json if it exists."""
    path = os.path.join(PROJECT_ROOT, "reports", "project_map.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


# ═══════════════════════════════════════════════════════════════════
# Filesystem scanners (from v1, extended)
# ═══════════════════════════════════════════════════════════════════

def scan_html_pages() -> list[dict]:
    pages = []
    site_dir = os.path.join(PROJECT_ROOT, "static", "site")
    if not os.path.isdir(site_dir):
        return pages
    for root, dirs, files in os.walk(site_dir):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and d != "assets"]
        for f in files:
            if f == "index.html":
                rel = os.path.relpath(os.path.join(root, f), PROJECT_ROOT).replace("\\", "/")
                site_rel = os.path.relpath(root, site_dir).replace("\\", "/")
                public_url = "/" if site_rel == "." else "/" + site_rel + "/"
                full_path = os.path.join(root, f)
                with open(full_path, encoding="utf-8", errors="replace") as fh:
                    first_line = fh.readline()
                generated = "GENERATED" in first_line
                title = _extract_html_title(full_path)
                pages.append({
                    "type": "html_page", "file": rel, "public_url": public_url,
                    "title": title, "generated": generated,
                    "provenance": "detected_from_code",
                })
    return pages


def scan_api_routes() -> list[dict]:
    routes = []
    routes_dir = os.path.join(PROJECT_ROOT, "apps", "api", "routes")
    if not os.path.isdir(routes_dir):
        return routes
    for fname in sorted(os.listdir(routes_dir)):
        if not fname.endswith(".py") or fname.startswith("_"):
            continue
        fpath = os.path.join(routes_dir, fname)
        rel = os.path.relpath(fpath, PROJECT_ROOT).replace("\\", "/")
        with open(fpath, encoding="utf-8") as f:
            content = f.read()
        prefix_match = re.search(r'prefix\s*=\s*["\']([^"\']+)["\']', content)
        prefix = prefix_match.group(1) if prefix_match else ""
        for m in re.finditer(
            r'@(?:router|public_router)\.(get|post|put|patch|delete)\(\s*["\']([^"\']+)["\']',
            content,
        ):
            method = m.group(1).upper()
            path = m.group(2)
            full_path = prefix + path if not path.startswith(prefix) else path
            line_start = content.rfind("\n", 0, m.start()) + 1
            decorator_line = content[line_start:m.end()]
            auth = "public_router" not in decorator_line
            routes.append({
                "type": "api_route", "method": method, "path": full_path,
                "auth_required": auth, "source_file": rel,
                "provenance": "detected_from_code",
            })
    return routes


def scan_python_packages() -> list[dict]:
    """Scan Python packages under apps/ with their modules and services."""
    packages = []
    apps_dir = os.path.join(PROJECT_ROOT, "apps")
    if not os.path.isdir(apps_dir):
        return packages
    for root, dirs, files in os.walk(apps_dir):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for f in sorted(files):
            if not f.endswith(".py") or f.startswith("_"):
                continue
            fpath = os.path.join(root, f)
            rel = os.path.relpath(fpath, PROJECT_ROOT).replace("\\", "/")
            with open(fpath, encoding="utf-8") as fh:
                content = fh.read()
            # Count functions/classes
            func_count = len(re.findall(r"^def \w+", content, re.MULTILINE))
            class_count = len(re.findall(r"^class \w+", content, re.MULTILINE))
            line_count = content.count("\n") + 1
            # Extract imports from other project modules
            imports = []
            for im in re.finditer(r"(?:from|import)\s+(apps\.[a-zA-Z0-9_.]+)", content):
                imports.append(im.group(1))
            # Detect deprecated
            deprecated = bool(re.search(r"(?:^|\n)\s*(?:#|\"\"\")\s*DEPRECATED", content[:500], re.IGNORECASE))
            packages.append({
                "type": "python_module", "file": rel,
                "functions": func_count, "classes": class_count, "lines": line_count,
                "internal_imports": sorted(set(imports)),
                "deprecated": deprecated,
                "provenance": "detected_from_code",
            })
    return packages


def scan_pathway_discovery_tests() -> list[dict]:
    """Scan tests inside apps/pathway_discovery/tests/."""
    tests = []
    test_dir = os.path.join(PROJECT_ROOT, "apps", "pathway_discovery", "tests")
    if not os.path.isdir(test_dir):
        return tests
    for f in sorted(os.listdir(test_dir)):
        if not f.endswith(".py") or f.startswith("_"):
            continue
        fpath = os.path.join(test_dir, f)
        rel = os.path.relpath(fpath, PROJECT_ROOT).replace("\\", "/")
        with open(fpath, encoding="utf-8") as fh:
            content = fh.read()
        test_count = len(re.findall(r"^def test_", content, re.MULTILINE))
        tests.append({
            "type": "test_file", "file": rel, "test_count": test_count,
            "provenance": "detected_from_code",
        })
    return tests


def scan_scripts() -> list[dict]:
    scripts = []
    for scan_dir in ["scripts", "deploy", "deploy/ops"]:
        full_dir = os.path.join(PROJECT_ROOT, scan_dir)
        if not os.path.isdir(full_dir):
            continue
        for fname in sorted(os.listdir(full_dir)):
            if fname.startswith(".") or fname.startswith("_"):
                continue
            if not (fname.endswith(".py") or fname.endswith(".sh")):
                continue
            fpath = os.path.join(full_dir, fname)
            if not os.path.isfile(fpath):
                continue
            rel = os.path.relpath(fpath, PROJECT_ROOT).replace("\\", "/")
            with open(fpath, encoding="utf-8", errors="replace") as f:
                head = f.read(500)
            deprecated = bool(re.search(r"(?:^|\n)\s*(?:#|\"\"\")\s*DEPRECATED", head, re.IGNORECASE))
            purpose = _extract_docstring(head, fname)
            scripts.append({
                "type": "script", "file": rel, "purpose": purpose,
                "deprecated": deprecated, "provenance": "detected_from_code",
            })
    return scripts


def scan_docs() -> list[dict]:
    docs = []
    for root, dirs, files in os.walk(os.path.join(PROJECT_ROOT, "docs")):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for f in sorted(files):
            if not f.endswith(".md"):
                continue
            fpath = os.path.join(root, f)
            rel = os.path.relpath(fpath, PROJECT_ROOT).replace("\\", "/")
            with open(fpath, encoding="utf-8", errors="replace") as fh:
                title = ""
                for line in fh:
                    if line.startswith("# "):
                        title = line[2:].strip()
                        break
            docs.append({"type": "doc", "file": rel, "title": title, "provenance": "detected_from_code"})
    return docs


def scan_tools() -> list[dict]:
    tools = []
    tools_dir = os.path.join(PROJECT_ROOT, "tools")
    if not os.path.isdir(tools_dir):
        return tools
    for fname in sorted(os.listdir(tools_dir)):
        if fname.startswith("."):
            continue
        fpath = os.path.join(tools_dir, fname)
        if not os.path.isfile(fpath):
            continue
        rel = os.path.relpath(fpath, PROJECT_ROOT).replace("\\", "/")
        with open(fpath, encoding="utf-8", errors="replace") as f:
            head = f.read(300)
        deprecated = bool(re.search(r"(?:^|\n)\s*(?:<!--|#|\"\"\")\s*DEPRECATED", head, re.IGNORECASE))
        tools.append({"type": "tool", "file": rel, "deprecated": deprecated, "provenance": "detected_from_code"})
    return tools


def scan_data_files() -> list[dict]:
    data = []
    data_dir = os.path.join(PROJECT_ROOT, "static", "site", "data", "boats")
    if os.path.isdir(data_dir):
        for fname in sorted(os.listdir(data_dir)):
            if fname.endswith(".json"):
                data.append({"type": "boat_data", "file": f"static/site/data/boats/{fname}", "provenance": "detected_from_code"})
    assets_dir = os.path.join(PROJECT_ROOT, "static", "site", "assets", "boats")
    if os.path.isdir(assets_dir):
        for slug in sorted(os.listdir(assets_dir)):
            manifest = os.path.join(assets_dir, slug, "manifest.json")
            if os.path.isfile(manifest):
                img_count = len([f for f in os.listdir(os.path.join(assets_dir, slug)) if f.endswith(".jpg")])
                data.append({
                    "type": "gallery_manifest", "file": f"static/site/assets/boats/{slug}/manifest.json",
                    "slug": slug, "image_count": img_count, "provenance": "detected_from_code",
                })
    return data


def scan_tests() -> list[dict]:
    tests = []
    tests_dir = os.path.join(PROJECT_ROOT, "tests")
    if not os.path.isdir(tests_dir):
        return tests
    for root, dirs, files in os.walk(tests_dir):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for f in sorted(files):
            if not f.endswith(".py") or f.startswith("_"):
                continue
            fpath = os.path.join(root, f)
            rel = os.path.relpath(fpath, PROJECT_ROOT).replace("\\", "/")
            with open(fpath, encoding="utf-8") as fh:
                content = fh.read()
            test_count = len(re.findall(r"^def test_", content, re.MULTILINE))
            tests.append({"type": "test_file", "file": rel, "test_count": test_count, "provenance": "detected_from_code"})
    return tests


def scan_static_assets() -> list[dict]:
    """Scan key static files at static/site/ root (JS, CSS, non-HTML)."""
    assets = []
    site_dir = os.path.join(PROJECT_ROOT, "static", "site")
    if not os.path.isdir(site_dir):
        return assets
    for f in sorted(os.listdir(site_dir)):
        if f.endswith((".js", ".css")):
            fpath = os.path.join(site_dir, f)
            if os.path.isfile(fpath):
                with open(fpath, encoding="utf-8", errors="replace") as fh:
                    first_line = fh.readline()
                generated = "GENERATED" in first_line
                assets.append({
                    "type": "static_asset", "file": f"static/site/{f}",
                    "generated": generated, "provenance": "detected_from_code",
                })
    return assets


def scan_config_files() -> list[dict]:
    configs = []
    for name in ["Dockerfile", "docker-compose.yml", "docker-compose.yaml",
                  "requirements.txt", ".gitignore", ".env.example",
                  "Caddyfile", "Caddyfile.sentyacht", "CLAUDE.md", ".claude/CLAUDE.md"]:
        if os.path.isfile(os.path.join(PROJECT_ROOT, name)):
            configs.append({"type": "config", "file": name, "provenance": "detected_from_code"})
    deploy_dir = os.path.join(PROJECT_ROOT, "deploy")
    if os.path.isdir(deploy_dir):
        for f in sorted(os.listdir(deploy_dir)):
            fpath = os.path.join(deploy_dir, f)
            if os.path.isfile(fpath) and not f.endswith(".py") and not f.endswith(".sh"):
                configs.append({"type": "config", "file": f"deploy/{f}", "provenance": "detected_from_code"})
    return configs


# ═══════════════════════════════════════════════════════════════════
# Reconciliation
# ═══════════════════════════════════════════════════════════════════

def reconcile(project_map: dict, audit_modules: list[dict], plan_blocks: list[dict]) -> list[dict]:
    """Cross-reference seed maps with scanned code. Return reconciled module list."""
    # Build a set of all files detected from code
    all_code_files = set()
    for category in project_map.values():
        if not isinstance(category, list):
            continue
        for item in category:
            if isinstance(item, dict) and "file" in item:
                all_code_files.add(item["file"])

    # Build basename index for fuzzy matching (scoring.py ->apps/api/services/scoring.py)
    basename_to_paths = {}
    for cf in all_code_files:
        bn = os.path.basename(cf)
        basename_to_paths.setdefault(bn, []).append(cf)

    reconciled = []
    for mod in audit_modules:
        entry = {
            "module": mod["name"],
            "audit_status": mod["status"],
            "plan_phase": None,
            "files_in_audit": mod["files_mentioned"],
            "files_confirmed_in_code": [],
            "files_missing_from_code": [],
            "provenance": "inherited_from_seed_map",
        }
        for f in mod["files_mentioned"]:
            if f in all_code_files or os.path.isfile(os.path.join(PROJECT_ROOT, f)):
                entry["files_confirmed_in_code"].append(f)
            else:
                # Basename fallback: "scoring.py" ->"apps/api/services/scoring.py"
                bn = os.path.basename(f)
                candidates = basename_to_paths.get(bn, [])
                if len(candidates) == 1:
                    entry["files_confirmed_in_code"].append(f"{f} ->{candidates[0]}")
                elif len(candidates) > 1:
                    entry["files_confirmed_in_code"].append(f"{f} ->(ambiguous: {len(candidates)} matches)")
                else:
                    entry["files_missing_from_code"].append(f)

        # Try to match with master plan block
        mod_lower = mod["name"].lower()
        for block in plan_blocks:
            if block["name"].lower() in mod_lower or mod_lower in block["name"].lower():
                entry["plan_phase"] = block["phase"]
                break

        # Determine validation status
        if entry["files_missing_from_code"]:
            entry["validation"] = "needs_validation"
        elif entry["files_confirmed_in_code"]:
            entry["validation"] = "confirmed"
        else:
            entry["validation"] = "no_files_to_check"

        reconciled.append(entry)

    # Check for plan blocks not in audit
    audit_names_lower = {m["name"].lower() for m in audit_modules}
    for block in plan_blocks:
        found = False
        for aname in audit_names_lower:
            if block["name"].lower() in aname or aname in block["name"].lower():
                found = True
                break
        if not found:
            reconciled.append({
                "module": block["name"],
                "audit_status": None,
                "plan_phase": block["phase"],
                "plan_description": block["description"],
                "files_in_audit": [],
                "files_confirmed_in_code": [],
                "files_missing_from_code": [],
                "provenance": "inherited_from_seed_map",
                "validation": "needs_validation",
            })

    return reconciled


def detect_drift(project_map: dict, audit_modules: list[dict]) -> list[dict]:
    """Compare scanned map against audit to find drift."""
    drift = []
    audit_path = os.path.join(PROJECT_ROOT, "docs", "openclaw_built_state_audit.md")
    if not os.path.isfile(audit_path):
        drift.append({"severity": "high", "issue": "Audit document not found", "detail": "docs/openclaw_built_state_audit.md missing"})
        return drift

    with open(audit_path, encoding="utf-8") as f:
        audit_content = f.read()

    # Pages documented as groups in the audit (not by individual URL).
    # These are explicit patterns — add new ones here if the audit groups more pages.
    GROUP_DOCUMENTED_PATTERNS = [
        "/barcos/",           # "24 detail pages" covers all ES boat pages
        "/boats/",            # "24 detail pages" covers all EN boat pages
        "/aviso-legal/",      # legal pages documented as a set
        "/politica-de-",      # politica-de-privacidad, politica-de-cookies
        "/legal-notice/",     # EN legal pages
        "/privacy-policy/",   # EN legal pages
        "/cookie-policy/",    # EN legal pages
        "/yates-en-venta/",   # catalog page documented under "Catálogo público"
        "/yachts-for-sale/",  # catalog page documented under "Catálogo público"
    ]

    # Check HTML pages
    for item in project_map.get("html_pages", []):
        url = item["public_url"]
        file_path = item["file"]
        # Skip pages covered by group documentation
        if any(pattern in url for pattern in GROUP_DOCUMENTED_PATTERNS):
            continue
        if url not in audit_content and file_path not in audit_content:
            drift.append({
                "severity": "medium",
                "issue": f"HTML page not in audit: {url}",
                "detail": f"File {file_path} exists but not mentioned in audit",
                "provenance": "detected_from_code",
            })

    # Route prefixes documented as groups in the audit.
    GROUP_DOCUMENTED_ROUTE_PREFIXES = [
        "/internal/admin/",   # admin routes documented as "10 endpoints admin"
    ]

    # Check API routes
    for item in project_map.get("api_routes", []):
        path = item["path"]
        # Skip routes covered by group documentation
        if any(path.startswith(prefix) for prefix in GROUP_DOCUMENTED_ROUTE_PREFIXES):
            continue
        path_pattern = re.sub(r"\{[^}]+\}", "{", path)
        found = path in audit_content
        if not found:
            for line in audit_content.split("\n"):
                if path_pattern in re.sub(r"\{[^}]+\}", "{", line):
                    found = True
                    break
        if not found:
            drift.append({
                "severity": "low",
                "issue": f"API route not in audit: {item['method']} {path}",
                "detail": f"Defined in {item['source_file']}",
                "provenance": "detected_from_code",
            })

    # Module paths documented as groups in the audit.
    GROUP_DOCUMENTED_MODULE_PREFIXES = [
        "apps/pathway_discovery/",  # documented as "10 archivos + 18 tests, ~5.000 líneas"
    ]

    # Check Python modules not referenced anywhere in docs
    for item in project_map.get("python_packages", []):
        f = item["file"]
        if any(f.startswith(prefix) for prefix in GROUP_DOCUMENTED_MODULE_PREFIXES):
            continue
        basename = os.path.basename(f)
        if basename not in audit_content and f not in audit_content:
            # Only flag non-trivial modules (>20 lines, not __init__)
            if item.get("lines", 0) > 20:
                drift.append({
                    "severity": "low",
                    "issue": f"Python module not in audit: {f}",
                    "detail": f"{item.get('lines', '?')} lines, {item.get('functions', '?')} functions",
                    "provenance": "detected_from_code",
                })

    return drift


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════

def _extract_html_title(path: str) -> str:
    with open(path, encoding="utf-8", errors="replace") as f:
        content = f.read(2000)
    m = re.search(r"<title>([^<]+)</title>", content)
    return m.group(1).strip() if m else ""


def _extract_docstring(head: str, fname: str) -> str:
    m = re.search(r'"""(.+?)"""', head, re.DOTALL)
    if m:
        return m.group(1).strip().split("\n")[0][:100]
    for line in head.split("\n"):
        if line.startswith("#") and not line.startswith("#!"):
            return line.lstrip("# ").strip()[:100]
    return fname


# ═══════════════════════════════════════════════════════════════════
# Output generators
# ═══════════════════════════════════════════════════════════════════

def write_json(data: dict, path: str):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, sort_keys=False)
        f.write("\n")


def write_markdown(project_map: dict, reconciled: list[dict], path: str):
    lines = [
        "# Project Map",
        "",
        f"Generated: {project_map['generated_at']}",
        "",
        "Auto-generated by `scripts/cartographer.py` v2. Do not edit manually.",
        "",
        "Provenance legend: `code` = detected from files, `seed` = from audit/plan docs, `inferred` = derived, `validate` = needs confirmation.",
        "",
    ]

    # Reconciled modules (the high-level view)
    lines.append("## Module Status (reconciled)")
    lines.append("")
    lines.append("| Module | Audit Status | Plan Phase | Files Confirmed | Validation |")
    lines.append("|---|---|---|---|---|")
    for r in reconciled:
        status = r.get("audit_status") or "—"
        phase = r.get("plan_phase") or "—"
        confirmed = len(r.get("files_confirmed_in_code", []))
        missing = len(r.get("files_missing_from_code", []))
        val = r.get("validation", "—")
        files_str = f"{confirmed} ok" + (f", {missing} missing" if missing else "")
        lines.append(f"| {r['module']} | {status} | {phase} | {files_str} | {val} |")

    # HTML pages
    lines.append("")
    lines.append("## HTML Pages")
    lines.append("")
    lines.append("| URL | Title | Generated | File |")
    lines.append("|---|---|---|---|")
    for p in sorted(project_map["html_pages"], key=lambda x: x["public_url"]):
        gen = "yes" if p["generated"] else "no"
        lines.append(f"| `{p['public_url']}` | {p['title'][:50]} | {gen} | `{p['file']}` |")

    # API routes
    lines.append("")
    lines.append("## API Routes")
    lines.append("")
    lines.append("| Method | Path | Auth | Source |")
    lines.append("|---|---|---|---|")
    for r in sorted(project_map["api_routes"], key=lambda x: x["path"]):
        auth = "key" if r["auth_required"] else "public"
        lines.append(f"| {r['method']} | `{r['path']}` | {auth} | `{r['source_file']}` |")

    # Python packages
    lines.append("")
    lines.append("## Python Modules")
    lines.append("")
    lines.append("| File | Lines | Functions | Imports | Deprecated |")
    lines.append("|---|---|---|---|---|")
    for p in sorted(project_map.get("python_packages", []), key=lambda x: x["file"]):
        imports = ", ".join(p.get("internal_imports", [])[:3])
        if len(p.get("internal_imports", [])) > 3:
            imports += "..."
        dep = "DEPRECATED" if p.get("deprecated") else ""
        lines.append(f"| `{p['file']}` | {p.get('lines', '?')} | {p.get('functions', '?')} | {imports} | {dep} |")

    # Scripts
    lines.append("")
    lines.append("## Scripts")
    lines.append("")
    lines.append("| File | Purpose | Deprecated |")
    lines.append("|---|---|---|")
    for s in project_map["scripts"]:
        dep = "DEPRECATED" if s["deprecated"] else ""
        lines.append(f"| `{s['file']}` | {s['purpose'][:60]} | {dep} |")

    # Data files
    lines.append("")
    lines.append("## Data Files")
    lines.append("")
    lines.append("| Type | File | Details |")
    lines.append("|---|---|---|")
    for d in project_map["data_files"]:
        detail = f"{d.get('image_count', '')} images" if d["type"] == "gallery_manifest" else ""
        lines.append(f"| {d['type']} | `{d['file']}` | {detail} |")

    # Static assets
    if project_map.get("static_assets"):
        lines.append("")
        lines.append("## Static Assets")
        lines.append("")
        lines.append("| File | Generated |")
        lines.append("|---|---|")
        for a in project_map["static_assets"]:
            gen = "yes" if a.get("generated") else "no"
            lines.append(f"| `{a['file']}` | {gen} |")

    # Tests (both main and pathway_discovery)
    lines.append("")
    lines.append("## Tests")
    lines.append("")
    all_tests = project_map.get("tests", []) + project_map.get("pathway_tests", [])
    total = sum(t["test_count"] for t in all_tests)
    lines.append(f"**Total: {total} test functions across {len(all_tests)} files**")
    lines.append("")
    lines.append("| File | Tests |")
    lines.append("|---|---|")
    for t in all_tests:
        lines.append(f"| `{t['file']}` | {t['test_count']} |")

    # Docs
    lines.append("")
    lines.append("## Documentation")
    lines.append("")
    lines.append("| File | Title |")
    lines.append("|---|---|")
    for d in project_map["docs"]:
        lines.append(f"| `{d['file']}` | {d['title'][:60]} |")

    # Tools + Configs
    lines.append("")
    lines.append("## Tools")
    lines.append("")
    for t in project_map["tools"]:
        dep = " (DEPRECATED)" if t.get("deprecated") else ""
        lines.append(f"- `{t['file']}`{dep}")

    lines.append("")
    lines.append("## Config Files")
    lines.append("")
    for c in project_map["configs"]:
        lines.append(f"- `{c['file']}`")

    lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def write_drift_report(drift: list[dict], reconciled: list[dict], temporal: dict, path: str):
    lines = [
        "# Project Drift Report",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "Reconciles 4 layers: audit doc, master plan, previous scan, and repo filesystem.",
        "",
    ]

    # Temporal diff section
    if temporal.get("available"):
        lines.append(f"## Changes since last scan ({temporal.get('previous_generated_at', '?')})")
        lines.append("")
        added = temporal.get("files_added", [])
        removed = temporal.get("files_removed", [])
        changes = temporal.get("category_changes", {})
        if not added and not removed and not changes:
            lines.append("No changes detected since last scan.")
        else:
            if added:
                lines.append(f"**Added ({len(added)}):**")
                for f in added:
                    lines.append(f"- `{f}`")
                lines.append("")
            if removed:
                lines.append(f"**Removed ({len(removed)}):**")
                for f in removed:
                    lines.append(f"- `{f}`")
                lines.append("")
            if changes:
                lines.append("**Category changes:**")
                for cat, d in changes.items():
                    lines.append(f"- {cat}: {d['previous']} ->{d['current']} ({d['delta']:+d})")
                lines.append("")
    else:
        lines.append("## Changes since last scan")
        lines.append("")
        lines.append("First run — no previous map to compare against.")
        lines.append("")

    # Reconciliation issues
    validation_issues = [r for r in reconciled if r.get("validation") == "needs_validation"]
    if validation_issues:
        lines.append("## Reconciliation: needs validation")
        lines.append("")
        for r in validation_issues:
            missing = r.get("files_missing_from_code", [])
            if missing:
                lines.append(f"- **{r['module']}** (audit: {r.get('audit_status', '?')}): files in audit but not in repo: {', '.join(missing)}")
            elif not r.get("audit_status"):
                lines.append(f"- **{r['module']}** (plan phase: {r.get('plan_phase', '?')}): in master plan but not in audit — {r.get('plan_description', '')}")
        lines.append("")

    # Filesystem drift
    if not drift:
        lines.append("## Filesystem drift")
        lines.append("")
        lines.append("**No drift detected.** Audit is in sync with the repo.")
    else:
        high = [d for d in drift if d["severity"] == "high"]
        medium = [d for d in drift if d["severity"] == "medium"]
        low = [d for d in drift if d["severity"] == "low"]
        lines.append(f"## Filesystem drift ({len(drift)} items: {len(high)} high, {len(medium)} medium, {len(low)} low)")
        lines.append("")
        for severity, items in [("High", high), ("Medium", medium), ("Low", low)]:
            if items:
                lines.append(f"### {severity}")
                lines.append("")
                for d in items:
                    lines.append(f"- **{d['issue']}**: {d['detail']}")
                lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ═══════════════════════════════════════════════════════════════════
# Temporal diff (previous_map comparison)
# ═══════════════════════════════════════════════════════════════════

def compute_temporal_diff(current_map: dict, prev_map: dict | None) -> dict:
    """Compare current scan with previous map to detect new/removed/changed items."""
    if not prev_map:
        return {"available": False}

    def _extract_files(m):
        files = set()
        for cat in m.values():
            if not isinstance(cat, list):
                continue
            for item in cat:
                if isinstance(item, dict) and "file" in item:
                    files.add(item["file"])
        return files

    prev_files = _extract_files(prev_map)
    curr_files = _extract_files(current_map)

    added = sorted(curr_files - prev_files)
    removed = sorted(prev_files - curr_files)

    # Count changes per category
    def _count(m, category):
        items = m.get(category, [])
        return len(items) if isinstance(items, list) else 0

    category_changes = {}
    for cat in ["html_pages", "api_routes", "python_packages", "scripts", "docs",
                "tools", "data_files", "static_assets", "tests", "pathway_tests", "configs"]:
        prev_count = _count(prev_map, cat)
        curr_count = _count(current_map, cat)
        if prev_count != curr_count:
            category_changes[cat] = {"previous": prev_count, "current": curr_count, "delta": curr_count - prev_count}

    return {
        "available": True,
        "previous_generated_at": prev_map.get("generated_at", "unknown"),
        "files_added": added,
        "files_removed": removed,
        "category_changes": category_changes,
    }


# ═══════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════

def main():
    print("=== Project Cartographer v2 ===\n")

    # Load seed maps
    print("Loading seed maps...")
    audit_modules = load_audit_seed()
    print(f"  Audit: {len(audit_modules)} modules")
    plan_blocks = load_master_plan_seed()
    print(f"  Master plan: {len(plan_blocks)} blocks")
    prev_map = load_previous_map()
    print(f"  Previous map: {'loaded' if prev_map else 'not found'}")

    # Scan filesystem
    print("\nScanning filesystem...")
    html_pages = scan_html_pages()
    print(f"  {len(html_pages)} HTML pages")
    api_routes = scan_api_routes()
    print(f"  {len(api_routes)} API routes")
    python_packages = scan_python_packages()
    print(f"  {len(python_packages)} Python modules")
    scripts = scan_scripts()
    print(f"  {len(scripts)} scripts")
    docs = scan_docs()
    print(f"  {len(docs)} docs")
    tools = scan_tools()
    print(f"  {len(tools)} tools")
    data_files = scan_data_files()
    print(f"  {len(data_files)} data files")
    static_assets = scan_static_assets()
    print(f"  {len(static_assets)} static assets")
    tests = scan_tests()
    pathway_tests = scan_pathway_discovery_tests()
    total_tests = sum(t["test_count"] for t in tests) + sum(t["test_count"] for t in pathway_tests)
    print(f"  {len(tests) + len(pathway_tests)} test files, {total_tests} test functions")
    configs = scan_config_files()
    print(f"  {len(configs)} config files")

    project_map = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "version": 2,
        "seed_maps_used": {
            "audit": "docs/openclaw_built_state_audit.md",
            "master_plan": "docs/openclaw_master_plan.md",
            "previous_map": "reports/project_map.json" if prev_map else None,
        },
        "html_pages": html_pages,
        "api_routes": api_routes,
        "python_packages": python_packages,
        "scripts": scripts,
        "docs": docs,
        "tools": tools,
        "data_files": data_files,
        "static_assets": static_assets,
        "tests": tests,
        "pathway_tests": pathway_tests,
        "configs": configs,
    }

    # Reconcile
    print("\nReconciling seed maps with code...")
    reconciled = reconcile(project_map, audit_modules, plan_blocks)
    confirmed = sum(1 for r in reconciled if r.get("validation") == "confirmed")
    needs_val = sum(1 for r in reconciled if r.get("validation") == "needs_validation")
    print(f"  {len(reconciled)} modules: {confirmed} confirmed, {needs_val} need validation")

    project_map["reconciled_modules"] = reconciled

    # Temporal diff
    print("\nComparing with previous map...")
    temporal = compute_temporal_diff(project_map, prev_map)
    if temporal["available"]:
        print(f"  +{len(temporal['files_added'])} added, -{len(temporal['files_removed'])} removed")
        for cat, delta in temporal.get("category_changes", {}).items():
            print(f"  {cat}: {delta['previous']} ->{delta['current']} ({delta['delta']:+d})")
    else:
        print("  No previous map — first run")
    project_map["temporal_diff"] = temporal

    # Detect drift
    print("\nDetecting drift...")
    drift = detect_drift(project_map, audit_modules)
    print(f"  {len(drift)} drift items")

    # Write outputs
    os.makedirs(os.path.join(PROJECT_ROOT, "reports"), exist_ok=True)

    json_path = os.path.join(PROJECT_ROOT, "reports", "project_map.json")
    write_json(project_map, json_path)
    print(f"\nWritten: reports/project_map.json")

    md_path = os.path.join(PROJECT_ROOT, "docs", "project_map.md")
    write_markdown(project_map, reconciled, md_path)
    print(f"Written: docs/project_map.md")

    drift_path = os.path.join(PROJECT_ROOT, "reports", "project_drift_report.md")
    write_drift_report(drift, reconciled, temporal, drift_path)
    print(f"Written: reports/project_drift_report.md")

    total_items = sum(len(v) for v in project_map.values() if isinstance(v, list))
    print(f"\n=== Done: {total_items} items mapped, {len(reconciled)} modules reconciled, {len(drift)} drift ===")


if __name__ == "__main__":
    main()
