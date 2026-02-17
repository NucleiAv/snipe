"""
Format string argument mismatch detection (C printf family).
#12: Wrong number of format specifiers vs arguments in printf/fprintf/sprintf.
"""
from __future__ import annotations
from typing import Any

from parser.symbol_extractor import Reference, Symbol
from analyzer.type_checker import Diagnostic


def check_format_strings(
    buffer_refs: list[Reference],
    buffer_symbols: list[Symbol],
    repo_symbols: list[dict[str, Any]],
    current_file: str,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if not current_file.endswith((".c", ".h")):
        return diagnostics

    for ref in buffer_refs:
        if ref.kind != "format_call":
            continue
        if ref.format_specifiers is None or ref.arg_count is None:
            continue
        if ref.format_specifiers != ref.arg_count:
            diagnostics.append(Diagnostic(
                file=current_file,
                line=ref.line,
                severity="ERROR",
                code="SNIPE_FORMAT_STRING",
                message=f"Format string in '{ref.name}' has {ref.format_specifiers} specifier(s) but {ref.arg_count} argument(s) provided.",
            ))

    return diagnostics
