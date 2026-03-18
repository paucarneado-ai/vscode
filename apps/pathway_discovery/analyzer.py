"""Analyze function-level interactions between modules via AST."""

import ast
import os

from apps.pathway_discovery.schemas import InteractionTrace
from apps.pathway_discovery.utils import file_to_module_id as _file_to_module_id


def _build_import_map(tree: ast.AST) -> dict[str, str]:
    """Map local names to their source modules.

    e.g. 'from apps.api.services.scoring import calculate_lead_score'
    -> {"calculate_lead_score": "apps.api.services.scoring"}
    """
    name_to_module: dict[str, str] = {}
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("apps."):
            for alias in node.names:
                local_name = alias.asname or alias.name
                name_to_module[local_name] = node.module
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("apps."):
                    local_name = alias.asname or alias.name
                    name_to_module[local_name] = alias.name
    return name_to_module


def _extract_call_name(node: ast.Call) -> tuple[str | None, str]:
    """Extract (object_name, function_name) from a Call node.

    Returns (None, "func") for direct calls, ("obj", "method") for attribute calls.
    """
    if isinstance(node.func, ast.Name):
        return None, node.func.id
    if isinstance(node.func, ast.Attribute):
        if isinstance(node.func.value, ast.Name):
            return node.func.value.id, node.func.attr
    return None, ""


def _get_arg_names(node: ast.Call) -> list[str]:
    """Best-effort extraction of argument representations."""
    args = []
    for a in node.args[:4]:  # Limit to first 4 args
        if isinstance(a, ast.Name):
            args.append(a.id)
        elif isinstance(a, ast.Attribute):
            args.append(ast.dump(a)[:40])
        elif isinstance(a, ast.Constant):
            args.append(repr(a.value)[:20])
        else:
            args.append("...")
    return args


class _CallVisitor(ast.NodeVisitor):
    """Walk a function body and collect Call nodes with their enclosing function."""

    def __init__(self):
        self.calls: list[tuple[str, ast.Call]] = []
        self._current_func: str = "<module>"

    def visit_FunctionDef(self, node):
        prev = self._current_func
        self._current_func = node.name
        self.generic_visit(node)
        self._current_func = prev

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, node):
        self.calls.append((self._current_func, node))
        self.generic_visit(node)


def analyze_interactions(root_path: str) -> list[InteractionTrace]:
    """Scan all .py files under root_path and extract function call interactions."""
    traces: list[InteractionTrace] = []

    py_files: list[str] = []
    for dirpath, _, filenames in os.walk(root_path):
        rel = os.path.relpath(dirpath, root_path).replace("\\", "/")
        if "pathway_discovery" in rel or "__pycache__" in rel:
            continue
        for fn in filenames:
            if fn.endswith(".py"):
                py_files.append(os.path.join(dirpath, fn))

    for fpath in py_files:
        try:
            with open(fpath, encoding="utf-8") as f:
                source = f.read()
            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError):
            continue

        caller_module = _file_to_module_id(fpath, root_path)
        import_map = _build_import_map(tree)
        rel_path = os.path.relpath(fpath, os.path.dirname(root_path)).replace("\\", "/")

        visitor = _CallVisitor()
        visitor.visit(tree)

        for func_name, call_node in visitor.calls:
            obj_name, method_name = _extract_call_name(call_node)
            if not method_name:
                continue

            # Resolve callee module
            callee_module = None
            resolution = "unresolved"
            confidence = 0.3
            reason = "could not resolve target module"

            if obj_name is None and method_name in import_map:
                # Direct imported function call: calculate_lead_score(...)
                callee_module = import_map[method_name]
                resolution = "direct"
                confidence = 0.95
                reason = f"directly imported from {callee_module}"
            elif obj_name and obj_name in import_map:
                # Attribute call on imported object: db.execute(...)
                callee_module = import_map[obj_name]
                resolution = "attribute"
                confidence = 0.7
                reason = f"attribute call on imported {obj_name} from {callee_module}"
            elif obj_name is None and method_name in ("print", "len", "str", "int", "dict",
                                                       "list", "set", "tuple", "range", "enumerate",
                                                       "isinstance", "hasattr", "getattr", "setattr",
                                                       "min", "max", "sum", "sorted", "round", "zip",
                                                       "map", "filter", "any", "all", "super", "type",
                                                       "open", "vars"):
                continue  # Skip builtins
            else:
                # Unresolved: local function, method on self, dynamic dispatch
                resolution = "unresolved" if obj_name else "local"
                confidence = 0.2 if obj_name else 0.1
                reason = "local or unresolvable call"
                continue  # Skip low-confidence noise in MVP

            traces.append(
                InteractionTrace(
                    caller_module=caller_module,
                    caller_function=func_name,
                    callee_module=callee_module,
                    callee_function=method_name,
                    line_number=call_node.lineno,
                    file_path=rel_path,
                    args_passed=_get_arg_names(call_node),
                    resolution_kind=resolution,
                    confidence=confidence,
                    confidence_reason=reason,
                )
            )

    return traces
