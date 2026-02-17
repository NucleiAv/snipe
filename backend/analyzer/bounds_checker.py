"""
Static array bounds verification.
Detects index usage beyond statically declared array bounds.
Uses canonical definition size from repo; extern declarations may declare wrong size.
"""
from __future__ import annotations
from typing import Any

from parser.symbol_extractor import Reference, Symbol
from analyzer.type_checker import Diagnostic


def _is_same_file(current_file: str, repo_file_path: str) -> bool:
    """Check if repo file path refers to the same file as current_file (handles path formats)."""
    if not repo_file_path:
        return False
    cur = current_file.replace("\\", "/")
    repo = repo_file_path.replace("\\", "/")
    return cur == repo or cur.endswith("/" + repo)


def check_array_bounds(
    buffer_refs: list[Reference],
    buffer_symbols: list[Symbol],
    repo_symbols: list[dict[str, Any]],
    current_file: str,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    # Repo + buffer arrays by name
    size_by_name: dict[str, int] = {}
    def_file: dict[str, str] = {}
    def_line: dict[str, int] = {}

    # Prefer canonical definition size from repo (other files); buffer extern
    # may declare wrong size - use actual definition for bounds checking
    for s in repo_symbols:
        if s.get("array_size") is None:
            continue
        if _is_same_file(current_file, s.get("file_path", "")):
            continue  # skip current file – buffer has unsaved version
        size_by_name[s["name"]] = s["array_size"]
        def_file[s["name"]] = s.get("file_path", "")
        def_line[s["name"]] = s.get("line", 0)
    for s in buffer_symbols:
        if s.array_size is not None and s.name not in size_by_name:
            size_by_name[s.name] = s.array_size
            def_file[s.name] = s.file_path or current_file
            def_line[s.name] = s.line

    for ref in buffer_refs:
        if ref.kind != "array_access" or ref.index_value is None:
            continue
        size = size_by_name.get(ref.name)
        if size is None:
            continue
        if ref.index_value < 0 or ref.index_value >= size:
            diagnostics.append(Diagnostic(
                file=current_file,
                line=ref.line,
                severity="ERROR",
                code="SNIPE_ARRAY_BOUNDS",
                message=f"Index {ref.index_value} exceeds declared size {size} for '{ref.name}' (declared in {def_file.get(ref.name, '?')}:{def_line.get(ref.name, '?')}).",
            ))
    return diagnostics
