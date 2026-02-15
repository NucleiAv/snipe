"""
Function signature drift detection.
Detects when a function call does not match the latest signature in the repo.
"""
from __future__ import annotations
from typing import Any

from parser.symbol_extractor import Reference
from analyzer.type_checker import Diagnostic


def check_function_signatures(
    buffer_refs: list[Reference],
    repo_symbols: list[dict[str, Any]],
    current_file: str,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    # Repo functions by name (prefer same file, then others)
    funcs: dict[str, dict] = {}
    for s in repo_symbols:
        if s.get("kind") != "function":
            continue
        name = s.get("name")
        if not name:
            continue
        if name not in funcs or s.get("file_path") == current_file:
            funcs[name] = s

    for ref in buffer_refs:
        if ref.kind != "call" or ref.arg_count is None:
            continue
        repo_def = funcs.get(ref.name)
        if not repo_def:
            continue
        expected = len(repo_def.get("params") or [])
        if ref.arg_count != expected:
            diagnostics.append(Diagnostic(
                file=current_file,
                line=ref.line,
                severity="WARNING",
                code="SNIPE_SIGNATURE_DRIFT",
                message=f"Function '{ref.name}' expects {expected} argument(s) but {ref.arg_count} provided (see {repo_def.get('file_path', '?')}:{repo_def.get('line', '?')}).",
            ))
    return diagnostics
