"""
Function argument type mismatch detection (Python).
#18: Calling a function with arguments of wrong types vs parameter annotations.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any

from parser.symbol_extractor import Reference, Symbol
from analyzer.type_checker import Diagnostic


def _get_language_from_path(file_path: str):
    ext = Path(file_path).suffix.lower()
    if ext == ".py":
        return "python"
    return None


def check_arg_types(
    buffer_refs: list[Reference],
    buffer_symbols: list[Symbol],
    repo_symbols: list[dict[str, Any]],
    current_file: str,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if _get_language_from_path(current_file) != "python":
        return diagnostics

    # Build function param type map from buffer + repo
    func_params: dict[str, list[dict]] = {}
    for sym in buffer_symbols:
        if sym.kind == "function" and sym.params:
            func_params[sym.name] = sym.params
    for s in repo_symbols:
        if s.get("kind") == "function" and s.get("params"):
            name = s.get("name")
            if name and name not in func_params:
                func_params[name] = s["params"]

    for ref in buffer_refs:
        if ref.kind != "call" or not ref.arg_types:
            continue
        if "." in ref.name:  # Skip method calls
            continue
        param_defs = func_params.get(ref.name)
        if not param_defs:
            continue

        # Match positional args to params (skip *args, **kwargs)
        regular_params = [p for p in param_defs if not p.get("name", "").startswith("*")]

        for i, arg_type in enumerate(ref.arg_types):
            if i >= len(regular_params):
                break
            if arg_type is None:
                continue  # Can't infer, skip
            param_type = regular_params[i].get("type")
            if param_type is None:
                continue  # No annotation, skip
            if arg_type != param_type:
                param_name = regular_params[i].get("name", f"arg{i}")
                diagnostics.append(Diagnostic(
                    file=current_file,
                    line=ref.line,
                    severity="ERROR",
                    code="SNIPE_ARG_TYPE_MISMATCH",
                    message=f"Argument '{param_name}' of '{ref.name}' expects type '{param_type}' but got '{arg_type}'.",
                ))

    return diagnostics
