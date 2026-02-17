"""
Dangerous C function detection.
#16: Flag use of unsafe C functions (strcpy, sprintf, gets, etc.).
"""
from __future__ import annotations
from typing import Any

from parser.symbol_extractor import Reference, Symbol
from analyzer.type_checker import Diagnostic

UNSAFE_FUNCTIONS = {
    "strcpy":   "Use strncpy() or strlcpy() instead",
    "strcat":   "Use strncat() or strlcat() instead",
    "sprintf":  "Use snprintf() instead",
    "gets":     "Use fgets() instead",
    "scanf":    "Use fgets() + sscanf() or limit field width (e.g. %99s)",
    "vsprintf": "Use vsnprintf() instead",
    "tmpnam":   "Use mkstemp() instead",
}


def check_unsafe_functions(
    buffer_refs: list[Reference],
    buffer_symbols: list[Symbol],
    repo_symbols: list[dict[str, Any]],
    current_file: str,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if not current_file.endswith((".c", ".h")):
        return diagnostics

    for ref in buffer_refs:
        if ref.kind != "call":
            continue
        suggestion = UNSAFE_FUNCTIONS.get(ref.name)
        if suggestion:
            diagnostics.append(Diagnostic(
                file=current_file,
                line=ref.line,
                severity="WARNING",
                code="SNIPE_UNSAFE_FUNCTION",
                message=f"'{ref.name}' is unsafe and can cause buffer overflows. {suggestion}.",
            ))

    return diagnostics
