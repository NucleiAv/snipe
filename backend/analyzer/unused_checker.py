"""
Unused declaration detection.
#13: Unused extern declarations in C
#14: Dead (unused) imports in Python
"""
from __future__ import annotations
from pathlib import Path
from typing import Any

from parser.symbol_extractor import Reference, Symbol
from analyzer.type_checker import Diagnostic


def check_unused_externs(
    buffer_refs: list[Reference],
    buffer_symbols: list[Symbol],
    repo_symbols: list[dict[str, Any]],
    current_file: str,
) -> list[Diagnostic]:
    """#13: Unused extern declarations in C."""
    diagnostics: list[Diagnostic] = []
    if not current_file.endswith((".c", ".h")):
        return diagnostics

    # Collect all referenced names in the buffer
    ref_names = {ref.name for ref in buffer_refs}

    for sym in buffer_symbols:
        if not sym.is_extern:
            continue
        if sym.name not in ref_names:
            diagnostics.append(Diagnostic(
                file=current_file,
                line=sym.line,
                severity="WARNING",
                code="SNIPE_UNUSED_EXTERN",
                message=f"Extern declaration '{sym.name}' is never used in this file.",
            ))

    return diagnostics


def check_dead_imports(
    buffer_refs: list[Reference],
    buffer_symbols: list[Symbol],
    repo_symbols: list[dict[str, Any]],
    current_file: str,
) -> list[Diagnostic]:
    """#14: Dead (unused) Python imports."""
    diagnostics: list[Diagnostic] = []
    if not current_file.endswith(".py"):
        return diagnostics

    # Collect all non-import reference names (reads, calls, etc.)
    used_names: set[str] = set()
    for ref in buffer_refs:
        if ref.kind != "import":
            used_names.add(ref.name)

    # Also count symbol names used in buffer (classes, functions defined here
    # may share a name with an import if it's used as a base class, etc.)
    for sym in buffer_symbols:
        # If a symbol references an imported name (e.g. @dataclass decorator),
        # the symbol itself uses that import
        pass  # The used_names from refs already covers identifier reads

    for ref in buffer_refs:
        if ref.kind != "import":
            continue
        if not ref.imported_names:
            continue
        for imp_name in ref.imported_names:
            if imp_name == "*":
                continue  # Can't check star imports
            if imp_name not in used_names:
                diagnostics.append(Diagnostic(
                    file=current_file,
                    line=ref.line,
                    severity="WARNING",
                    code="SNIPE_DEAD_IMPORT",
                    message=f"Imported name '{imp_name}' is never used in this file.",
                ))

    return diagnostics
