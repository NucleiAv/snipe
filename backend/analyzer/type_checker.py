"""
Cross-file type consistency detection.
Detects when a symbol is used with a different type than declared in the repo.
Only checks same-language files (C with C, Python with Python).
"""
from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass
from typing import Any

from parser.symbol_extractor import Symbol, Reference


@dataclass
class Diagnostic:
    file: str
    line: int
    severity: str  # ERROR, WARNING
    message: str
    code: str = ""


def _get_language_from_path(file_path: str) -> str | None:
    """Return language for file: 'c' for .c/.h, 'python' for .py, else None."""
    ext = Path(file_path).suffix.lower()
    if ext in (".c", ".h"):
        return "c"
    if ext == ".py":
        return "python"
    return None


def _is_same_file(current_file: str, repo_file_path: str) -> bool:
    """Check if repo file path refers to the same file as current_file (handles path formats)."""
    if not repo_file_path:
        return False
    cur = current_file.replace("\\", "/")
    repo = repo_file_path.replace("\\", "/")
    return cur == repo or cur.endswith("/" + repo)


def check_type_mismatch(
    buffer_refs: list[Reference],
    buffer_symbols: list[Symbol],
    repo_symbols: list[dict[str, Any]],
    current_file: str,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    current_lang = _get_language_from_path(current_file)
    if current_lang is None:
        return diagnostics

    # Build local type map from current buffer symbols
    local_types = {s.name: s.type for s in buffer_symbols if s.type is not None}
    local_types.update((s.name, s.kind) for s in buffer_symbols if s.name not in local_types)

    # Repo symbol map by name (same language only; prefer definitions over extern)
    repo_by_name: dict[str, dict] = {}
    for s in repo_symbols:
        if _is_same_file(current_file, s.get("file_path", "")):
            continue  # skip same-file, we use buffer symbols
        repo_lang = _get_language_from_path(s.get("file_path", ""))
        if repo_lang != current_lang:
            continue  # skip cross-language
        name = s.get("name")
        if not name:
            continue
        existing = repo_by_name.get(name)
        # Prefer non-extern (definition) over extern as canonical type
        if name not in repo_by_name:
            repo_by_name[name] = s
        elif existing and existing.get("is_extern") and not s.get("is_extern"):
            repo_by_name[name] = s  # definition overrides extern

    # 1. Check buffer declarations (incl. extern) vs repo definitions – type and array size
    # Only report when current file has extern (wrong declaration); definition file is canonical
    # Track symbols with declaration-level type mismatch to avoid redundant ref-level checks
    declaration_mismatch_names: set[str] = set()
    for sym in buffer_symbols:
        if not getattr(sym, "is_extern", False):
            continue  # current file has definition – errors go to files with wrong extern
        repo_def = repo_by_name.get(sym.name)
        if not repo_def:
            continue
        repo_type = (repo_def.get("type") or repo_def.get("kind") or "").strip()
        buf_type = (sym.type or sym.kind or "").strip()
        type_mismatch = buf_type and repo_type and buf_type != repo_type
        repo_size = repo_def.get("array_size")
        buf_size = sym.array_size
        # Array size mismatch: extern declares larger than actual (overclaims bounds)
        size_mismatch = (
            buf_size is not None
            and repo_size is not None
            and buf_size > repo_size
        )
        if type_mismatch:
            declaration_mismatch_names.add(sym.name)
            diagnostics.append(Diagnostic(
                file=current_file,
                line=sym.line,
                severity="ERROR",
                code="SNIPE_TYPE_MISMATCH",
                message=f"'{sym.name}' is declared as {repo_type} in {repo_def.get('file_path', '?')}:{repo_def.get('line', '?')} but declared as {buf_type} here.",
            ))
        if size_mismatch:
            diagnostics.append(Diagnostic(
                file=current_file,
                line=sym.line,
                severity="ERROR",
                code="SNIPE_ARRAY_BOUNDS",
                message=f"'{sym.name}' declares size {buf_size} but actual size is {repo_size} (in {repo_def.get('file_path', '?')}:{repo_def.get('line', '?')}).",
            ))

    # 2. Check array_write: assigning wrong type to array element (e.g. int to char[])
    buffer_symbols_by_name = {s.name: s for s in buffer_symbols}
    for ref in buffer_refs:
        if ref.kind != "array_write":
            continue
        rhs_type = ref.inferred_type or (local_types.get(ref.rhs_name) if ref.rhs_name else None)
        if not rhs_type:
            continue
        elem_type = None
        elem_file = current_file
        elem_line = 0
        sym = buffer_symbols_by_name.get(ref.name)
        if sym and sym.type:
            elem_type = sym.type.strip()
            elem_line = sym.line
        else:
            repo_def = repo_by_name.get(ref.name)
            if repo_def:
                elem_type = (repo_def.get("type") or repo_def.get("kind") or "").strip()
                elem_file = repo_def.get("file_path", "?")
                elem_line = repo_def.get("line", 0)
        if elem_type and rhs_type and elem_type != rhs_type:
            diagnostics.append(Diagnostic(
                file=current_file,
                line=ref.line,
                severity="ERROR",
                code="SNIPE_TYPE_MISMATCH",
                message=f"Assigning {rhs_type} to '{ref.name}' (element type {elem_type} in {elem_file}:{elem_line}).",
            ))

    # 3. Check references (read, array_access) vs repo definitions; skip if we already
    # reported declaration-level type mismatch for that symbol
    ref_diagnostics: list[Diagnostic] = []
    for ref in buffer_refs:
        if ref.kind not in ("read", "array_access"):
            continue
        if ref.name in declaration_mismatch_names:
            continue
        repo_def = repo_by_name.get(ref.name)
        if not repo_def or repo_def.get("is_extern"):
            continue  # skip extern – definition is canonical; errors reported in extern's file
        repo_type = repo_def.get("type") or repo_def.get("kind") or ""
        ref_type = ref.inferred_type or local_types.get(ref.name)
        if ref_type and repo_type and str(ref_type).strip() != str(repo_type).strip():
            ref_diagnostics.append(Diagnostic(
                file=current_file,
                line=ref.line,
                severity="ERROR",
                code="SNIPE_TYPE_MISMATCH",
                message=f"'{ref.name}' is declared as {repo_type} in {repo_def.get('file_path', '?')}:{repo_def.get('line', '?')} but used as {ref_type} here.",
            ))
    diagnostics.extend(ref_diagnostics)
    return diagnostics
