"""
Return type mismatch detection (Python).
#15: Return statement type doesn't match function's declared return type annotation.
"""
from __future__ import annotations
from typing import Any

from parser.symbol_extractor import Reference, Symbol
from analyzer.type_checker import Diagnostic


def check_return_types(
    buffer_refs: list[Reference],
    buffer_symbols: list[Symbol],
    repo_symbols: list[dict[str, Any]],
    current_file: str,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if not current_file.endswith(".py"):
        return diagnostics

    for ref in buffer_refs:
        if ref.kind != "return_value":
            continue
        if not ref.declared_return_type or not ref.return_value_type:
            continue
        # Normalize types for comparison
        declared = ref.declared_return_type.strip()
        actual = ref.return_value_type.strip()
        if declared != actual:
            diagnostics.append(Diagnostic(
                file=current_file,
                line=ref.line,
                severity="ERROR",
                code="SNIPE_TYPE_MISMATCH",
                message=f"Return type '{actual}' does not match declared return type '{declared}' for function '{ref.name}'.",
            ))

    return diagnostics
