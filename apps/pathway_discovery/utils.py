"""Shared utilities for pathway_discovery."""

import os


def file_to_module_id(file_path: str, root_path: str) -> str:
    """Convert a file path to a dotted module ID relative to root_path's parent."""
    rel = os.path.relpath(file_path, os.path.dirname(root_path))
    rel = rel.replace("\\", "/")
    if rel.endswith("/__init__.py"):
        rel = rel[: -len("/__init__.py")]
    elif rel.endswith(".py"):
        rel = rel[:-3]
    return rel.replace("/", ".")
