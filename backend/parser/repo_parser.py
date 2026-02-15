"""
Recursively scan repository and extract symbols into a symbol table.
Persists to repo_symbols.json.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Optional

from .symbol_extractor import Symbol, extract_symbols_from_source


# Default ignore patterns
DEFAULT_IGNORE = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
    ".eggs", "*.egg-info", ".tox", ".mypy_cache", ".pytest_cache", "vendor"
}

SUPPORTED_EXTENSIONS = {".py", ".c", ".h"}


def should_ignore(path: Path, base: Path) -> bool:
    rel = path.relative_to(base) if base in path.parents or path == base else path
    parts = rel.parts
    for part in parts:
        if part in DEFAULT_IGNORE or part.startswith(".") and part != ".py":
            return True
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return True
    return False


def build_repo_symbol_table(repo_path: str | Path, output_json_path: Optional[str | Path] = None) -> list[dict]:
    import logging
    repo_path = Path(repo_path).resolve()
    if not repo_path.is_dir():
        return []

    symbols: list[Symbol] = []
    files_scanned = 0
    for file_path in repo_path.rglob("*"):
        if not file_path.is_file():
            continue
        if should_ignore(file_path, repo_path):
            continue
        try:
            source = file_path.read_bytes()
        except Exception as e:
            logging.getLogger(__name__).warning("Could not read %s: %s", file_path, e)
            continue
        files_scanned += 1
        rel_path = str(file_path.relative_to(repo_path))
        extracted = extract_symbols_from_source(source, rel_path)
        for s in extracted:
            s.file_path = rel_path
            symbols.append(s)

    logging.getLogger(__name__).info("Scanned %d supported files, got %d symbols", files_scanned, len(symbols))
    data = [s.to_dict() for s in symbols]
    if output_json_path is not None:
        out = Path(output_json_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    return data
