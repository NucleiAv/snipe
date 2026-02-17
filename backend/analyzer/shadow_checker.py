"""
Variable shadowing detection.
#11: Local variable inside a function shadows a module-level variable (Python).
"""
from __future__ import annotations
from pathlib import Path
from typing import Any

from parser.symbol_extractor import Reference, Symbol
from analyzer.type_checker import Diagnostic


def check_variable_shadowing(
    buffer_refs: list[Reference],
    buffer_symbols: list[Symbol],
    repo_symbols: list[dict[str, Any]],
    current_file: str,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    ext = Path(current_file).suffix.lower()
    if ext != ".py":
        return diagnostics

    # Module-level symbols (scope == "") in current buffer
    module_level_names: dict[str, Symbol] = {}
    for s in buffer_symbols:
        if s.scope == "" and s.kind == "variable":
            module_level_names[s.name] = s

    # Also check repo-level module symbols from same language files
    for s in repo_symbols:
        if s.get("scope", "") == "" and s.get("kind") == "variable":
            fp = s.get("file_path", "")
            if fp.endswith(".py"):
                name = s.get("name")
                if name and name not in module_level_names:
                    module_level_names[name] = None  # Mark as known at module level

    # Check scoped symbols (scope != "") against module-level
    for s in buffer_symbols:
        if s.scope == "" or s.kind != "variable":
            continue
        if s.name in module_level_names:
            outer = module_level_names[s.name]
            if outer and isinstance(outer, Symbol):
                diagnostics.append(Diagnostic(
                    file=current_file,
                    line=s.line,
                    severity="WARNING",
                    code="SNIPE_SHADOWED_SYMBOL",
                    message=f"Local variable '{s.name}' in '{s.scope}' shadows module-level variable defined at line {outer.line}.",
                ))
            else:
                diagnostics.append(Diagnostic(
                    file=current_file,
                    line=s.line,
                    severity="WARNING",
                    code="SNIPE_SHADOWED_SYMBOL",
                    message=f"Local variable '{s.name}' in '{s.scope}' shadows a module-level variable in the repository.",
                ))

    return diagnostics
