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
        params = repo_def.get("params") or []
        is_variadic = repo_def.get("is_variadic", False)

        # Filter out *args/**kwargs params for counting
        regular_params = [p for p in params if not p.get("name", "").startswith("*")]
        min_args = sum(1 for p in regular_params if not p.get("has_default", False))
        max_args = float("inf") if is_variadic else len(regular_params)

        if ref.arg_count < min_args or ref.arg_count > max_args:
            # Build descriptive expectation string
            if is_variadic:
                expected_str = f"at least {min_args}"
            elif min_args == max_args:
                expected_str = f"{min_args}"
            else:
                expected_str = f"{min_args} to {int(max_args)}"
            diagnostics.append(Diagnostic(
                file=current_file,
                line=ref.line,
                severity="ERROR",
                code="SNIPE_SIGNATURE_DRIFT",
                message=f"Function '{ref.name}' expects {expected_str} argument(s) but {ref.arg_count} provided (see {repo_def.get('file_path', '?')}:{repo_def.get('line', '?')}).",
            ))
    return diagnostics