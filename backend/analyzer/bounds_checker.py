"""
Static array bounds verification.
Detects index usage beyond statically declared array bounds.
"""
from __future__ import annotations
from typing import Any

from parser.symbol_extractor import Reference, Symbol
from analyzer.type_checker import Diagnostic


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

    for s in repo_symbols:
        if s.get("array_size") is not None:
            size_by_name[s["name"]] = s["array_size"]
            def_file[s["name"]] = s.get("file_path", "")
            def_line[s["name"]] = s.get("line", 0)
    for s in buffer_symbols:
        if s.array_size is not None:
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
