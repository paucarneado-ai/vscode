"""Codebase map generator for OpenClaw.

Scans the project structure (API routes, services, governance, skills,
integrations) and produces a self-contained interactive HTML file with
a D3.js force-directed graph.

Usage:
    python scripts/generate_map.py
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
# Allow override via environment variable (used in Docker container)
_env_root = os.environ.get("PROJECT_ROOT")
PROJECT_ROOT = Path(_env_root) if _env_root else SCRIPT_DIR.parent

# Template and output: check SCRIPT_DIR first (Docker), then PROJECT_ROOT (local)
def _find(name: str, *search_dirs: Path) -> Path:
    for d in search_dirs:
        p = d / name
        if p.exists():
            return p
    return search_dirs[0] / name  # fallback to first

TEMPLATE_PATH = _find("static/codebase-map-template.html", SCRIPT_DIR.parent, SCRIPT_DIR, PROJECT_ROOT)
OUTPUT_DIR = SCRIPT_DIR.parent / "static" if not _env_root else SCRIPT_DIR / "static"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_PATH = OUTPUT_DIR / "codebase-map.html"
D3_LOCAL = _find("d3.v7.min.js", SCRIPT_DIR, SCRIPT_DIR.parent / "scripts")
D3_CDN = "https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js"
DAGRE_LOCAL = _find("dagre.min.js", SCRIPT_DIR, SCRIPT_DIR.parent / "scripts")
DAGRE_CDN = "https://cdn.jsdelivr.net/npm/@dagrejs/dagre@1.1.4/dist/dagre.min.js"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Node:
    id: str
    label: str
    type: str          # entrypoint|route|function|table|schema|governance|skill|external|file
    layer: int         # 1=API, 2=Governance, 3=Integrations
    file: str = ""     # relative path from project root
    line: int = 0
    group: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class Edge:
    source: str
    target: str
    type: str          # includes|calls|imports|consumes|governs|uses_schema|writes_table
    label: str = ""


class GraphBuilder:
    """Accumulates nodes and edges with automatic deduplication."""

    def __init__(self) -> None:
        self._nodes: dict[str, Node] = {}
        self._edges: dict[tuple[str, str, str], Edge] = {}
        self.groups: dict[str, dict[str, Any]] = {}

    def add_node(self, **kwargs: Any) -> Node:
        node = Node(**kwargs)
        self._nodes[node.id] = node
        return node

    def add_edge(self, **kwargs: Any) -> Edge:
        edge = Edge(**kwargs)
        key = (edge.source, edge.target, edge.type)
        self._edges[key] = edge
        return edge

    def add_group(self, key: str, label: str, layer: int) -> None:
        self.groups[key] = {"label": label, "layer": layer}

    def has_node(self, node_id: str) -> bool:
        return node_id in self._nodes

    def find_node_by_label_prefix(self, prefix: str) -> str | None:
        """Find a node whose label starts with *prefix*."""
        for nid, n in self._nodes.items():
            if n.label.startswith(prefix):
                return nid
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [asdict(n) for n in self._nodes.values()],
            "edges": [asdict(e) for e in self._edges.values()],
            "groups": self.groups,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rel(path: Path) -> str:
    """Return a forward-slash relative path from PROJECT_ROOT."""
    try:
        return str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _read(path: Path) -> str:
    """Read file content, return empty string if missing."""
    try:
        return path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return ""


def _balanced_paren_block(text: str, start: int) -> str:
    """Extract text from *start* (pointing at '(') until matching ')'."""
    depth = 0
    i = start
    while i < len(text):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
        i += 1
    return text[start:]


# ---------------------------------------------------------------------------
# Layer 1 – API Scanner
# ---------------------------------------------------------------------------

ROUTE_DECORATOR_RE = re.compile(
    r"@router\.(get|post|put|delete|patch)\(",
    re.IGNORECASE,
)
FUNC_DEF_RE = re.compile(r"^(?:async\s+)?def\s+(\w+)\(", re.MULTILINE)
SERVICE_IMPORT_RE = re.compile(
    r"from\s+apps\.api\.services\.(\w+)\s+import\s+(.+)"
)
SCHEMA_CLASS_RE = re.compile(r"^class\s+(\w+)\(.*(?:BaseModel|Base)\):", re.MULTILINE)
CREATE_TABLE_RE = re.compile(r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+(\w+)", re.IGNORECASE)
COLUMN_RE = re.compile(r"^\s+(\w+)\s+(TEXT|INTEGER|REAL|BLOB)", re.IGNORECASE | re.MULTILINE)
INCLUDE_ROUTER_RE = re.compile(r"app\.include_router\(\s*(\w+)")
RESPONSE_MODEL_RE = re.compile(r"response_model\s*=\s*(\w+)")


class APIScanner:
    """Layer 1: FastAPI routes, services, database, schemas."""

    def __init__(self, graph: GraphBuilder, root: Path) -> None:
        self.g = graph
        self.root = root

    def scan(self) -> None:
        self._setup_groups()
        self._scan_main()
        self._scan_routes()
        self._scan_services()
        self._scan_db()
        self._scan_schemas()

    # -- groups --

    def _setup_groups(self) -> None:
        self.g.add_group("core", "Core App", 1)
        self.g.add_group("health_routes", "Health Routes", 1)
        self.g.add_group("leads_routes", "Lead Routes", 1)
        self.g.add_group("internal_routes", "Internal Routes", 1)
        self.g.add_group("demo_routes", "Demo Routes", 1)
        self.g.add_group("scoring_service", "Scoring Service", 1)
        self.g.add_group("leadpack_service", "Lead Pack Service", 1)
        self.g.add_group("actions_service", "Actions Service", 1)
        self.g.add_group("database", "Database", 1)
        self.g.add_group("schemas", "Pydantic Schemas", 1)

    # -- main.py --

    def _scan_main(self) -> None:
        path = self.root / "apps" / "api" / "main.py"
        text = _read(path)
        self.g.add_node(
            id="entrypoint:main",
            label="FastAPI App",
            type="entrypoint",
            layer=1,
            file=_rel(path),
            line=1,
            group="core",
            details={"title": "OpenClaw", "version": "0.1.0"},
        )
        for m in INCLUDE_ROUTER_RE.finditer(text):
            router_var = m.group(1)
            group_map = {
                "health_router": "health_routes",
                "leads_router": "leads_routes",
                "internal_router": "internal_routes",
                "demo_router": "demo_routes",
            }
            group = group_map.get(router_var, "core")
            self.g.add_edge(
                source="entrypoint:main",
                target=f"group:{group}",
                type="includes",
                label=router_var,
            )

    # -- routes --

    ROUTE_FILES = {
        "health": ("apps/api/routes/health.py", "health_routes"),
        "leads": ("apps/api/routes/leads.py", "leads_routes"),
        "internal": ("apps/api/routes/internal.py", "internal_routes"),
        "demo": ("apps/api/routes/demo.py", "demo_routes"),
    }

    def _scan_routes(self) -> None:
        for module_name, (rel_path, group) in self.ROUTE_FILES.items():
            path = self.root / rel_path.replace("/", os.sep)
            text = _read(path)
            if not text:
                # File missing – create placeholder
                self.g.add_node(
                    id=f"route:{module_name}:missing",
                    label=f"{module_name} (missing)",
                    type="route",
                    layer=1,
                    file=rel_path,
                    line=0,
                    group=group,
                    details={"status": "missing"},
                )
                continue

            # Discover service imports → build edges later
            service_imports: dict[str, list[str]] = {}
            for m in SERVICE_IMPORT_RE.finditer(text):
                svc = m.group(1)
                names = [n.strip().rstrip(",") for n in m.group(2).split(",")]
                service_imports[svc] = names

            # Parse route decorators
            lines = text.split("\n")
            i = 0
            while i < len(lines):
                line = lines[i]
                dm = ROUTE_DECORATOR_RE.search(line)
                if dm:
                    method = dm.group(1).upper()
                    # Get the full decorator argument block
                    dec_start = text.index(line)
                    paren_pos = text.index("(", dec_start + dm.start())
                    block = _balanced_paren_block(text, paren_pos)
                    # Extract path from first string literal in block
                    path_match = re.search(r'["\']([^"\']+)["\']', block)
                    route_path = path_match.group(1) if path_match else "?"
                    full_path = route_path

                    # Extract response_model if present
                    resp_match = RESPONSE_MODEL_RE.search(block)
                    resp_model = resp_match.group(1) if resp_match else None

                    # Find the handler function name (next def after decorator)
                    handler = "unknown"
                    for j in range(i + 1, min(i + 5, len(lines))):
                        fm = FUNC_DEF_RE.match(lines[j])
                        if fm:
                            handler = fm.group(1)
                            break

                    node_id = f"route:{module_name}:{method}:{full_path}"
                    details: dict[str, Any] = {
                        "method": method,
                        "handler": handler,
                    }
                    if resp_model:
                        details["response_model"] = resp_model

                    self.g.add_node(
                        id=node_id,
                        label=f"{method} {full_path}",
                        type="route",
                        layer=1,
                        file=rel_path,
                        line=i + 1,
                        group=group,
                        details=details,
                    )

                    # Edges to services based on handler body heuristic
                    for svc, funcs in service_imports.items():
                        for func_name in funcs:
                            # Check if handler body (next ~50 lines) calls this function
                            body_text = "\n".join(lines[i : min(i + 60, len(lines))])
                            if func_name in body_text:
                                target_id = f"service:{svc}:{func_name}"
                                self.g.add_edge(
                                    source=node_id,
                                    target=target_id,
                                    type="calls",
                                    label=func_name,
                                )

                    # Edge to response schema
                    if resp_model:
                        schema_id = f"schema:{resp_model}"
                        self.g.add_edge(
                            source=node_id,
                            target=schema_id,
                            type="uses_schema",
                        )
                i += 1

    # -- services --

    SERVICE_FILES = {
        "scoring": ("apps/api/services/scoring.py", "scoring_service"),
        "leadpack": ("apps/api/services/leadpack.py", "leadpack_service"),
        "actions": ("apps/api/services/actions.py", "actions_service"),
    }

    def _scan_services(self) -> None:
        for svc_name, (rel_path, group) in self.SERVICE_FILES.items():
            path = self.root / rel_path.replace("/", os.sep)
            text = _read(path)
            if not text:
                continue
            # Find top-level function definitions
            for m in re.finditer(r"^def\s+(\w+)\(", text, re.MULTILINE):
                func = m.group(1)
                if func.startswith("_"):
                    continue  # skip private helpers
                line_num = text[: m.start()].count("\n") + 1
                self.g.add_node(
                    id=f"service:{svc_name}:{func}",
                    label=f"{func}()",
                    type="function",
                    layer=1,
                    file=rel_path,
                    line=line_num,
                    group=group,
                    details={"module": svc_name},
                )

    # -- database --

    def _scan_db(self) -> None:
        path = self.root / "apps" / "api" / "db.py"
        text = _read(path)
        if not text:
            return

        for m in CREATE_TABLE_RE.finditer(text):
            table_name = m.group(1)
            line_num = text[: m.start()].count("\n") + 1
            # Extract columns for this table (scan until next CREATE TABLE or end)
            next_table = CREATE_TABLE_RE.search(text, m.end())
            table_block = text[m.start() : next_table.start() if next_table else len(text)]
            columns = [cm.group(1) for cm in COLUMN_RE.finditer(table_block)]

            self.g.add_node(
                id=f"table:{table_name}",
                label=table_name,
                type="table",
                layer=1,
                file=_rel(path),
                line=line_num,
                group="database",
                details={"columns": columns},
            )

    # -- schemas --

    def _scan_schemas(self) -> None:
        path = self.root / "apps" / "api" / "schemas.py"
        text = _read(path)
        if not text:
            return

        for m in SCHEMA_CLASS_RE.finditer(text):
            name = m.group(1)
            line_num = text[: m.start()].count("\n") + 1
            self.g.add_node(
                id=f"schema:{name}",
                label=name,
                type="schema",
                layer=1,
                file=_rel(path),
                line=line_num,
                group="schemas",
                details={},
            )


# ---------------------------------------------------------------------------
# Layer 2 – Governance Scanner
# ---------------------------------------------------------------------------

SECTION_RE = re.compile(r"^##\s+(?:\d+\.\s+)?(.+)", re.MULTILINE)


class GovernanceScanner:
    """Layer 2: CLAUDE.md rules, skills, task tracking."""

    def __init__(self, graph: GraphBuilder, root: Path) -> None:
        self.g = graph
        self.root = root

    def scan(self) -> None:
        self._setup_groups()
        self._scan_claude_files()
        self._scan_skills()
        self._scan_tasks()

    def _setup_groups(self) -> None:
        self.g.add_group("governance", "Governance Rules", 2)
        self.g.add_group("module_rules", "Module Rules", 2)
        self.g.add_group("skills", "Skills / Agents", 2)
        self.g.add_group("tasks", "Task Tracking", 2)

    def _scan_claude_files(self) -> None:
        # Global CLAUDE.md
        global_path = self.root / ".claude" / "CLAUDE.md"
        self._parse_claude_md(global_path, "global", "governance")

        # Module-local CLAUDE.md files
        for local in [
            self.root / "apps" / "api" / "automations" / "CLAUDE.md",
            self.root / "core" / "CLAUDE.md",
        ]:
            module_name = local.parent.name
            self._parse_claude_md(local, module_name, "module_rules")

    def _parse_claude_md(self, path: Path, scope: str, group: str) -> None:
        text = _read(path)
        if not text:
            return
        for m in SECTION_RE.finditer(text):
            title = m.group(1).strip()
            line_num = text[: m.start()].count("\n") + 1
            safe_title = re.sub(r"[^a-z0-9_]+", "_", title.lower()).strip("_")
            node_id = f"governance:{scope}:{safe_title}"
            self.g.add_node(
                id=node_id,
                label=title,
                type="governance",
                layer=2,
                file=_rel(path),
                line=line_num,
                group=group,
                details={"scope": scope},
            )

    def _scan_skills(self) -> None:
        skills_dir = self.root / "skills"
        if not skills_dir.is_dir():
            return
        for item in sorted(skills_dir.iterdir()):
            if item.is_dir():
                # Skill is a directory — look for SKILL.md or any .md
                md_files = list(item.glob("*.md"))
                skill_name = item.name
                skill_file = md_files[0] if md_files else item
                self.g.add_node(
                    id=f"skill:{skill_name}",
                    label=skill_name,
                    type="skill",
                    layer=2,
                    file=_rel(skill_file),
                    line=1,
                    group="skills",
                    details={},
                )
            elif item.suffix == ".md":
                skill_name = item.stem
                self.g.add_node(
                    id=f"skill:{skill_name}",
                    label=skill_name,
                    type="skill",
                    layer=2,
                    file=_rel(item),
                    line=1,
                    group="skills",
                    details={},
                )

        # Also scan skills/operational/ if it exists
        op_dir = skills_dir / "operational"
        if op_dir.is_dir():
            for md in sorted(op_dir.glob("*.md")):
                if md.name == "CLAUDE.md":
                    continue
                skill_name = md.stem
                if not self.g.has_node(f"skill:{skill_name}"):
                    self.g.add_node(
                        id=f"skill:{skill_name}",
                        label=skill_name,
                        type="skill",
                        layer=2,
                        file=_rel(md),
                        line=1,
                        group="skills",
                        details={"category": "operational"},
                    )

    def _scan_tasks(self) -> None:
        for name in ["todo.md", "lessons.md"]:
            path = self.root / "tasks" / name
            if path.exists():
                self.g.add_node(
                    id=f"file:tasks/{name}",
                    label=name,
                    type="file",
                    layer=2,
                    file=_rel(path),
                    line=1,
                    group="tasks",
                    details={},
                )


# ---------------------------------------------------------------------------
# Layer 3 – Integration Scanner
# ---------------------------------------------------------------------------

N8N_ENDPOINT_RE = re.compile(r"(GET|POST|PUT|DELETE)\s+(/[^\s\)`]+)")
DOCKER_SERVICE_RE = re.compile(r"^\s+(\w[\w-]*):\s*$", re.MULTILINE)


class IntegrationScanner:
    """Layer 3: n8n, webhooks, external forms, docker."""

    def __init__(self, graph: GraphBuilder, root: Path) -> None:
        self.g = graph
        self.root = root

    def scan(self) -> None:
        self._setup_groups()
        self._scan_n8n()
        self._scan_external_sources()
        self._scan_docker()

    def _setup_groups(self) -> None:
        self.g.add_group("integrations", "External Systems", 3)
        self.g.add_group("deployment", "Deployment", 3)

    def _scan_n8n(self) -> None:
        path = self.root / "docs" / "integration" / "n8n_interface.md"
        text = _read(path)
        if not text:
            return

        self.g.add_node(
            id="external:n8n",
            label="n8n (Automation)",
            type="external",
            layer=3,
            file=_rel(path),
            line=1,
            group="integrations",
            details={"type": "automation_platform"},
        )

        seen: set[str] = set()
        for m in N8N_ENDPOINT_RE.finditer(text):
            method = m.group(1)
            endpoint = m.group(2)
            # Normalize: strip trailing punctuation
            endpoint = endpoint.rstrip(".,;:)")
            key = f"{method} {endpoint}"
            if key in seen:
                continue
            seen.add(key)
            # Try to find matching route node
            target = self._find_route_node(method, endpoint)
            if target:
                self.g.add_edge(
                    source="external:n8n",
                    target=target,
                    type="consumes",
                    label=key,
                )

    def _find_route_node(self, method: str, endpoint: str) -> str | None:
        """Attempt to find a route node matching method + endpoint."""
        # Clean endpoint: remove query strings, trailing punctuation
        clean = endpoint.split("?")[0].rstrip(".,;:)`")
        # Strip /api prefix (n8n docs reference /api/leads but routes are /leads)
        if clean.startswith("/api/"):
            clean = clean[4:]  # /api/leads → /leads
        # Normalize {lead_id} vs {id} — n8n uses {id}, routes use {lead_id}
        clean_generic = re.sub(r"\{[^}]+\}", "{id}", clean)

        for module in ["health", "leads", "internal", "demo"]:
            candidate = f"route:{module}:{method}:{clean}"
            if self.g.has_node(candidate):
                return candidate
            # Try with generic param
            for nid in list(self.g._nodes):
                if not nid.startswith(f"route:{module}:{method}:"):
                    continue
                nid_generic = re.sub(r"\{[^}]+\}", "{id}", nid)
                expected = f"route:{module}:{method}:{clean_generic}"
                if nid_generic == expected:
                    return nid
        return None

    def _scan_external_sources(self) -> None:
        # Webhook providers
        self.g.add_node(
            id="external:webhooks",
            label="Webhook Providers",
            type="external",
            layer=3,
            file="",
            line=0,
            group="integrations",
            details={"type": "inbound_webhook"},
        )
        target = self._find_route_node("POST", "/leads/webhook/{provider}")
        if target:
            self.g.add_edge(
                source="external:webhooks",
                target=target,
                type="consumes",
                label="POST /leads/webhook/{provider}",
            )

        # External forms / landing pages
        self.g.add_node(
            id="external:forms",
            label="External Forms",
            type="external",
            layer=3,
            file="",
            line=0,
            group="integrations",
            details={"type": "lead_intake"},
        )
        target = self._find_route_node("POST", "/leads/external")
        if target:
            self.g.add_edge(
                source="external:forms",
                target=target,
                type="consumes",
                label="POST /leads/external",
            )

    def _scan_docker(self) -> None:
        path = self.root / "docker-compose.yml"
        text = _read(path)
        if not text:
            return
        for m in DOCKER_SERVICE_RE.finditer(text):
            svc = m.group(1)
            if svc in ("version", "services", "volumes", "networks"):
                continue
            self.g.add_node(
                id=f"deploy:{svc}",
                label=f"Docker: {svc}",
                type="external",
                layer=3,
                file=_rel(path),
                line=text[: m.start()].count("\n") + 1,
                group="deployment",
                details={"type": "docker_service"},
            )


# ---------------------------------------------------------------------------
# Cross-layer edges
# ---------------------------------------------------------------------------

def add_cross_layer_edges(g: GraphBuilder) -> None:
    """Add heuristic edges between layers (governance → API, skills → areas)."""
    # Governance approval boundaries → protected files
    protected = [
        ("README.md", "file"),
        ("Dockerfile", "file"),
        ("docker-compose", "file"),
        (".gitignore", "file"),
    ]
    approval_node = None
    for nid in list(g._nodes):
        if "approval_boundaries" in nid or "approval" in nid.lower():
            approval_node = nid
            break
    if approval_node:
        for label, _ in protected:
            g.add_edge(
                source=approval_node,
                target=f"protected:{label}",
                type="governs",
                label=f"protects {label}",
            )

    # Skill → API area heuristic edges
    skill_area_map = {
        "architecture_guardian": "core",
        "regression_sentinel": "leads_routes",
        "auto_test_generator": "leads_routes",
        "type_safety_guard": "schemas",
        "clean_code_enforcer": "core",
        "safe_scaffolder": "core",
    }
    for skill, area in skill_area_map.items():
        skill_id = f"skill:{skill}"
        group_id = f"group:{area}"
        if g.has_node(skill_id):
            g.add_edge(source=skill_id, target=group_id, type="governs", label="watches")


# ---------------------------------------------------------------------------
# D3.js embedding
# ---------------------------------------------------------------------------

def _get_lib_source(local_path: Path, cdn_url: str, name: str) -> str | None:
    """Return JS library source, downloading and caching if needed."""
    if local_path.exists():
        return local_path.read_text(encoding="utf-8")
    try:
        from urllib.request import urlopen, Request
        print(f"  Downloading {name} from CDN (one-time)...")
        req = Request(cdn_url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urlopen(req, timeout=30)
        code = resp.read().decode("utf-8")
        local_path.write_text(code, encoding="utf-8")
        print(f"  Cached at {local_path}")
        return code
    except Exception as e:
        print(f"  Warning: Could not download {name}: {e}")
        return None


def get_d3_source() -> str | None:
    return _get_lib_source(D3_LOCAL, D3_CDN, "D3.js v7")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def generate() -> None:
    print("OpenClaw Codebase Map Generator")
    print(f"  Project root: {PROJECT_ROOT}")

    # Build graph
    g = GraphBuilder()
    print("  Scanning Layer 1 (API)...")
    APIScanner(g, PROJECT_ROOT).scan()
    print("  Scanning Layer 2 (Governance)...")
    GovernanceScanner(g, PROJECT_ROOT).scan()
    print("  Scanning Layer 3 (Integrations)...")
    IntegrationScanner(g, PROJECT_ROOT).scan()
    print("  Adding cross-layer edges...")
    add_cross_layer_edges(g)

    data = g.to_dict()
    data["meta"] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project": "OpenClaw",
        "node_count": len(data["nodes"]),
        "edge_count": len(data["edges"]),
    }

    print(f"  Graph: {data['meta']['node_count']} nodes, {data['meta']['edge_count']} edges")

    # Read template
    if not TEMPLATE_PATH.exists():
        print(f"  ERROR: Template not found at {TEMPLATE_PATH}")
        print("  Create the template first, then re-run this script.")
        sys.exit(1)

    template = TEMPLATE_PATH.read_text(encoding="utf-8")

    # Embed D3.js
    d3_source = get_d3_source()
    if d3_source:
        template = template.replace("/*__D3_INLINE__*/", d3_source)

    # Embed Dagre.js
    dagre_source = _get_lib_source(DAGRE_LOCAL, DAGRE_CDN, "Dagre")
    if dagre_source:
        template = template.replace("/*__DAGRE_INLINE__*/", dagre_source)

    # Inject graph data — replace the placeholder AND its fallback object
    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    html = template.replace(
        '/*__GRAPH_DATA__*/{"nodes":[],"edges":[],"groups":{},"meta":{}}',
        json_str,
    )

    # Write output
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(f"  Output: {OUTPUT_PATH}")

    # Git hook reminder
    git_dir = PROJECT_ROOT / ".git"
    if git_dir.is_dir():
        hook_path = git_dir / "hooks" / "post-commit"
        if not hook_path.exists():
            print("\n  TIP: Install the post-commit hook to auto-regenerate:")
            print(f"    cp scripts/hooks/post-commit {hook_path}")
            print(f"    chmod +x {hook_path}")
    else:
        print("\n  Note: No .git repo found. The post-commit hook will be")
        print("  available at scripts/hooks/post-commit once you git init.")

    print("\nDone! Open static/codebase-map.html in your browser.")


if __name__ == "__main__":
    generate()
