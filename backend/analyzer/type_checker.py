"""
Cross-file type consistency detection.
Detects when a symbol is used with a different type than declared in the repo.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from parser.symbol_extractor import Symbol, Reference


@dataclass
class Diagnostic:
    file: str
    line: int
    severity: str  # ERROR, WARNING
    message: str
    code: str = ""


def check_type_mismatch(
    buffer_refs: list[Reference],
    buffer_symbols: list[Symbol],
    repo_symbols: list[dict[str, Any]],
    current_file: str,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    # Build local type map from current buffer symbols
    local_types = {s.name: s.type for s in buffer_symbols if s.type is not None}
    local_types.update((s.name, s.kind) for s in buffer_symbols if s.name not in local_types)

    # Repo symbol map by name (first definition wins for simplicity; could use scope)
    repo_by_name: dict[str, dict] = {}
    for s in repo_symbols:
        if s.get("file_path") == current_file:
            continue  # skip same-file, we use buffer symbols
        name = s.get("name")
        if name and name not in repo_by_name:
            repo_by_name[name] = s

    for ref in buffer_refs:
        if ref.kind not in ("read", "array_access"):
            continue
        repo_def = repo_by_name.get(ref.name)
        if not repo_def:
            continue
        repo_type = repo_def.get("type") or repo_def.get("kind") or ""
        ref_type = ref.inferred_type or local_types.get(ref.name)
        if ref_type and repo_type and str(ref_type).strip() != str(repo_type).strip():
            diagnostics.append(Diagnostic(
                file=current_file,
                line=ref.line,
                severity="WARNING",
                code="SNIPE_TYPE_MISMATCH",
                message=f"'{ref.name}' is declared as {repo_type} in {repo_def.get('file_path', '?')}:{repo_def.get('line', '?')} but used as {ref_type} here.",
            ))
    return diagnostics
