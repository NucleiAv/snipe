"""
Parse unsaved buffer content and extract symbols/references for live analysis.
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional

from .symbol_extractor import (
    Symbol,
    Reference,
    extract_symbols_from_source,
    extract_references_from_source,
)


def get_language_from_path(file_path: str) -> Optional[str]:
    ext = Path(file_path).suffix.lower()
    if ext == ".py":
        return "python"
    if ext in (".c", ".h"):
        return "c"
    return None


def parse_unsaved_buffer(
    buffer_content: str,
    file_path: str,
    language: Optional[str] = None,
) -> tuple[list[Symbol], list[Reference]]:
    if language is None:
        language = get_language_from_path(file_path)
    if language is None:
        return [], []
    source = buffer_content.encode("utf-8")
    symbols = extract_symbols_from_source(source, file_path, language)
    refs = extract_references_from_source(source, file_path, language)
    return symbols, refs
