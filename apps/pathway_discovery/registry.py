"""Build module and function registry from Python AST."""

import ast
import os

from apps.pathway_discovery.schemas import (
    FunctionRegistryEntry,
    ModuleRegistryEntry,
    PathwayRegistryEntry,
)
from apps.pathway_discovery.utils import file_to_module_id as _file_to_module_id

PROTECTED_KEYWORDS = {"scoring", "db", "auth"}


def _classify_module_kind(file_path: str) -> str:
    parts = file_path.replace("\\", "/").lower()
    if "/routes/" in parts:
        return "route"
    if "/services/" in parts:
        return "service"
    if parts.endswith("schemas.py"):
        return "schema"
    if parts.endswith("config.py") or parts.endswith("db.py"):
        return "infra"
    if "/utils/" in parts or parts.endswith("utils.py"):
        return "util"
    return "other"


def _is_protected(module_id: str, file_path: str) -> bool:
    combined = (module_id + file_path).lower()
    return any(kw in combined for kw in PROTECTED_KEYWORDS)


def _extract_imports(tree: ast.AST) -> list[str]:
    """Extract module-level import targets."""
    imports = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return imports


def _extract_functions(tree: ast.AST) -> list[tuple[str, int, list[str], int]]:
    """Return list of (name, lineno, arg_names, line_count)."""
    results = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = [a.arg for a in node.args.args]
            end = getattr(node, "end_lineno", node.lineno)
            results.append((node.name, node.lineno, args, end - node.lineno + 1))
    return results


def _extract_classes(tree: ast.AST) -> list[str]:
    return [n.name for n in ast.iter_child_nodes(tree) if isinstance(n, ast.ClassDef)]


def build_registry(
    root_path: str,
) -> tuple[list[ModuleRegistryEntry], list[FunctionRegistryEntry], list[PathwayRegistryEntry]]:
    """Scan all .py files under root_path and build the registry."""
    modules: list[ModuleRegistryEntry] = []
    functions: list[FunctionRegistryEntry] = []
    pathways: list[PathwayRegistryEntry] = []

    # Collect all Python files
    py_files: list[str] = []
    for dirpath, _, filenames in os.walk(root_path):
        # Skip pathway_discovery itself and __pycache__
        rel = os.path.relpath(dirpath, root_path).replace("\\", "/")
        if "pathway_discovery" in rel or "__pycache__" in rel:
            continue
        for fn in filenames:
            if fn.endswith(".py"):
                py_files.append(os.path.join(dirpath, fn))

    # Build module entries
    module_map: dict[str, ModuleRegistryEntry] = {}
    for fpath in py_files:
        try:
            with open(fpath, encoding="utf-8") as f:
                source = f.read()
            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError):
            continue

        mid = _file_to_module_id(fpath, root_path)
        rel_path = os.path.relpath(fpath, os.path.dirname(root_path)).replace("\\", "/")
        imports = _extract_imports(tree)
        funcs = _extract_functions(tree)
        classes = _extract_classes(tree)
        line_count = source.count("\n") + 1

        entry = ModuleRegistryEntry(
            module_id=mid,
            file_path=rel_path,
            module_kind=_classify_module_kind(rel_path),
            functions=[name for name, _, _, _ in funcs],
            classes=classes,
            imports_from=[i for i in imports if i.startswith("apps.")],
            imported_by=[],
            line_count=line_count,
            fan_out=0,
            fan_in=0,
            protected=_is_protected(mid, rel_path),
        )
        module_map[mid] = entry
        modules.append(entry)

        for name, lineno, args, lc in funcs:
            functions.append(
                FunctionRegistryEntry(
                    module_id=mid,
                    function_name=name,
                    line_number=lineno,
                    arg_names=args,
                    line_count=lc,
                )
            )

    # Build imported_by and fan-in/fan-out
    all_mids = set(module_map.keys())
    for mid, entry in module_map.items():
        targets = set()
        for imp in entry.imports_from:
            # Resolve "apps.api.services.scoring" or partial matches
            for target_mid in all_mids:
                if imp == target_mid or imp.startswith(target_mid + ".") or target_mid.startswith(imp):
                    targets.add(target_mid)
        entry.fan_out = len(targets)
        for t in targets:
            if t in module_map and t != mid:
                module_map[t].imported_by.append(mid)

    for entry in modules:
        entry.fan_in = len(entry.imported_by)

    # Build pathways from import relationships
    pathway_id_counter = 0
    for mid, entry in module_map.items():
        for imp in entry.imports_from:
            for target_mid in all_mids:
                if target_mid != mid and (
                    imp == target_mid or imp.startswith(target_mid + ".") or target_mid.startswith(imp)
                ):
                    pathway_id_counter += 1
                    pathways.append(
                        PathwayRegistryEntry(
                            pathway_id=f"PW-{pathway_id_counter:03d}",
                            source_module=mid,
                            target_module=target_mid,
                            via_import=imp,
                            hop_count=1,
                        )
                    )

    return modules, functions, pathways
