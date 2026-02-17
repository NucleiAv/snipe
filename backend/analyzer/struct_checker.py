"""
Struct member access validation (C).
#19: Accessing a member that doesn't exist on the struct type,
     or accessing a member on a variable that is not of the correct struct type.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any

from parser.symbol_extractor import Reference, Symbol
from analyzer.type_checker import Diagnostic


def check_struct_access(
    buffer_refs: list[Reference],
    buffer_symbols: list[Symbol],
    repo_symbols: list[dict[str, Any]],
    current_file: str,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if not current_file.endswith((".c", ".h")):
        return diagnostics

    # Build variable -> type map
    var_types: dict[str, str] = {}
    for sym in buffer_symbols:
        if sym.type:
            var_types[sym.name] = sym.type
    for s in repo_symbols:
        name = s.get("name")
        if name and s.get("type") and name not in var_types:
            var_types[name] = s["type"]

    # Build struct -> members map
    struct_members: dict[str, list[dict]] = {}
    for sym in buffer_symbols:
        if sym.kind == "struct" and sym.members:
            struct_members[sym.name] = sym.members
    for s in repo_symbols:
        if s.get("kind") == "struct" and s.get("members"):
            name = s.get("name")
            if name and name not in struct_members:
                struct_members[name] = s["members"]

    for ref in buffer_refs:
        if ref.kind != "member_access":
            continue
        if not ref.member_name:
            continue

        var_type = var_types.get(ref.name)
        if not var_type:
            continue

        # Extract struct name from type (e.g. "struct Point" -> "Point")
        struct_name = None
        if var_type.startswith("struct "):
            struct_name = var_type.split()[-1]

        if struct_name is None:
            continue

        members = struct_members.get(struct_name)
        if members is None:
            continue  # Struct definition not found, skip

        member_names = {m["name"] for m in members}
        if ref.member_name not in member_names:
            diagnostics.append(Diagnostic(
                file=current_file,
                line=ref.line,
                severity="ERROR",
                code="SNIPE_STRUCT_ACCESS",
                message=f"Struct '{struct_name}' has no member '{ref.member_name}'. Available members: {', '.join(sorted(member_names))}.",
            ))

    return diagnostics
