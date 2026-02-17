"""
Assignment type mismatch detection (Python).
#17: Assigning a value of wrong type to a type-annotated variable.
"""
from __future__ import annotations
from typing import Any

from parser.symbol_extractor import Reference, Symbol
from analyzer.type_checker import Diagnostic


def check_assignment_types(
    buffer_refs: list[Reference],
    buffer_symbols: list[Symbol],
    repo_symbols: list[dict[str, Any]],
    current_file: str,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if not current_file.endswith(".py"):
        return diagnostics

    for ref in buffer_refs:
        if ref.kind != "assignment":
            continue
        if not ref.annotation_type or not ref.inferred_type:
            continue
        if ref.annotation_type != ref.inferred_type:
            diagnostics.append(Diagnostic(
                file=current_file,
                line=ref.line,
                severity="ERROR",
                code="SNIPE_TYPE_MISMATCH",
                message=f"Variable '{ref.name}' is annotated as '{ref.annotation_type}' but assigned a value of type '{ref.inferred_type}'.",
            ))

    return diagnostics
