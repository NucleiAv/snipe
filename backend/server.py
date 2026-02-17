"""
Snipe local analysis server.
Exposes HTTP API for the VSCode extension: analyze buffer, get repo symbols, get graph.
"""
from __future__ import annotations
import json
import logging
from pathlib import Path
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Run from backend directory so these imports work
from parser.repo_parser import build_repo_symbol_table
from parser.buffer_parser import parse_unsaved_buffer
from analyzer.type_checker import check_type_mismatch
from analyzer.bounds_checker import check_array_bounds
from analyzer.signature_checker import check_function_signatures
from analyzer.type_checker import Diagnostic
from analyzer.undefined_checker import check_undefined_symbols
from analyzer.shadow_checker import check_variable_shadowing
from analyzer.format_checker import check_format_strings
from analyzer.unused_checker import check_unused_externs, check_dead_imports
from analyzer.return_checker import check_return_types
from analyzer.safety_checker import check_unsafe_functions
from analyzer.assignment_checker import check_assignment_types
from analyzer.arg_type_checker import check_arg_types
from analyzer.struct_checker import check_struct_access
from graph.repo_graph import build_repo_graph


app = FastAPI(title="Snipe Analysis Server", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory repo symbols; (re)built on first analyze or explicit refresh
_repo_symbols: list[dict[str, Any]] = []
_repo_path: Optional[str] = None
_data_dir: Path = Path(__file__).resolve().parent / "data"
_symbols_path: Path = _data_dir / "repo_symbols.json"


@app.get("/")
def root() -> dict:
    """Snipe API. Use /docs for Swagger or /health to check server."""
    return {"name": "Snipe Analysis Server", "docs": "/docs", "health": "/health"}


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    """Avoid 404 when browser requests favicon."""
    from fastapi.responses import Response
    return Response(status_code=204)


class OpenBuffer(BaseModel):
    content: str
    file_path: str


class AnalyzeRequest(BaseModel):
    content: str
    file_path: str
    repo_path: str
    language: Optional[str] = None
    open_buffers: Optional[list[OpenBuffer]] = None


class RefreshRequest(BaseModel):
    repo_path: str


_repo_mtime: float = 0.0  # max mtime of supported files at last index


def _max_repo_mtime(repo_path: str) -> float:
    """Return the max modification time of supported files in the repo."""
    import os
    max_mt = 0.0
    for root, dirs, files in os.walk(repo_path):
        # Skip ignored dirs in-place
        dirs[:] = [d for d in dirs if d not in {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build"}]
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in (".c", ".h", ".py"):
                try:
                    mt = os.path.getmtime(os.path.join(root, f))
                    if mt > max_mt:
                        max_mt = mt
                except OSError:
                    pass
    return max_mt


def _ensure_repo_symbols(repo_path: str, force: bool = False) -> list[dict]:
    global _repo_symbols, _repo_path, _repo_mtime
    current_mtime = _max_repo_mtime(repo_path)
    needs_rebuild = force or _repo_path != repo_path or not _repo_symbols or current_mtime > _repo_mtime
    if needs_rebuild:
        _repo_path = repo_path
        _symbols_path.parent.mkdir(parents=True, exist_ok=True)
        _repo_symbols = build_repo_symbol_table(repo_path, output_json_path=_symbols_path)
        _repo_mtime = current_mtime
    return _repo_symbols


def _diagnostic_to_dict(d: Diagnostic) -> dict:
    return {
        "file": d.file,
        "line": d.line,
        "severity": d.severity,
        "message": d.message,
        "code": d.code or "",
    }


@app.post("/analyze")
def analyze(request: AnalyzeRequest) -> dict:
    """Analyze unsaved buffer against repo knowledge graph. Returns diagnostics."""
    repo_path = str(Path(request.repo_path).resolve())
    if not Path(repo_path).is_dir():
        raise HTTPException(status_code=400, detail="Invalid repo_path")
    repo_symbols = _ensure_repo_symbols(repo_path)
    buffer_symbols, buffer_refs = parse_unsaved_buffer(
        request.content, request.file_path, request.language
    )
    current_file = request.file_path
    diagnostics: list[Diagnostic] = []
    repo_dicts = [s if isinstance(s, dict) else s.to_dict() for s in repo_symbols]

    # Overlay unsaved open buffers: re-extract symbols from other editors' content
    # so cross-file checks use live (unsaved) types, not stale on-disk versions.
    if request.open_buffers:
        from parser.symbol_extractor import extract_symbols_from_source
        # Collect file paths that have live buffers (normalize to relative)
        overlay_files: set[str] = set()
        overlay_symbols: list[dict] = []
        for ob in request.open_buffers:
            rel = ob.file_path
            try:
                rel = str(Path(ob.file_path).relative_to(Path(repo_path)))
            except (ValueError, TypeError):
                pass
            rel = rel.replace("\\", "/")
            overlay_files.add(rel)
            syms = extract_symbols_from_source(ob.content.encode("utf-8"), rel)
            for s in syms:
                s.file_path = rel
                overlay_symbols.append(s.to_dict())
        # Remove repo symbols from overlay files and replace with live ones
        repo_dicts = [s for s in repo_dicts if s.get("file_path", "").replace("\\", "/") not in overlay_files]
        repo_dicts.extend(overlay_symbols)
    diagnostics.extend(check_type_mismatch(buffer_refs, buffer_symbols, repo_dicts, current_file))
    diagnostics.extend(check_array_bounds(buffer_refs, buffer_symbols, repo_dicts, current_file))
    diagnostics.extend(check_function_signatures(buffer_refs, repo_dicts, current_file))
    # --- New checks (#9-#19) ---
    diagnostics.extend(check_undefined_symbols(buffer_refs, buffer_symbols, repo_dicts, current_file))
    diagnostics.extend(check_variable_shadowing(buffer_refs, buffer_symbols, repo_dicts, current_file))
    diagnostics.extend(check_format_strings(buffer_refs, buffer_symbols, repo_dicts, current_file))
    diagnostics.extend(check_unused_externs(buffer_refs, buffer_symbols, repo_dicts, current_file))
    diagnostics.extend(check_dead_imports(buffer_refs, buffer_symbols, repo_dicts, current_file))
    diagnostics.extend(check_return_types(buffer_refs, buffer_symbols, repo_dicts, current_file))
    diagnostics.extend(check_unsafe_functions(buffer_refs, buffer_symbols, repo_dicts, current_file))
    diagnostics.extend(check_assignment_types(buffer_refs, buffer_symbols, repo_dicts, current_file))
    diagnostics.extend(check_arg_types(buffer_refs, buffer_symbols, repo_dicts, current_file))
    diagnostics.extend(check_struct_access(buffer_refs, buffer_symbols, repo_dicts, current_file))
    # Deduplicate diagnostics (same file, line, code, message)
    seen: set[tuple] = set()
    unique_diagnostics: list[Diagnostic] = []
    for d in diagnostics:
        key = (d.file, d.line, d.code, d.message)
        if key not in seen:
            seen.add(key)
            unique_diagnostics.append(d)
    diagnostics = unique_diagnostics
    log.info("Analyze %s: %d buffer_refs, %d diagnostics", current_file, len(buffer_refs), len(diagnostics))
    return {
        "diagnostics": [_diagnostic_to_dict(d) for d in diagnostics],
        "file": current_file,
    }


@app.post("/refresh")
def refresh(request: RefreshRequest) -> dict:
    """Rescan repository and rebuild symbol table."""
    raw = request.repo_path
    repo_path = str(Path(raw).resolve())
    log.info("Refresh: raw repo_path=%r resolved=%r is_dir=%s", raw, repo_path, Path(repo_path).is_dir())
    if not Path(repo_path).is_dir():
        raise HTTPException(status_code=400, detail=f"Invalid repo_path: {repo_path!r}")
    symbols = build_repo_symbol_table(repo_path, output_json_path=_symbols_path)
    global _repo_symbols, _repo_path
    _repo_symbols = symbols
    _repo_path = repo_path
    log.info("Refresh: extracted %d symbols from %s", len(symbols), repo_path)
    return {"symbol_count": len(symbols), "repo_path": repo_path}


@app.get("/symbols")
def get_symbols(repo_path: str) -> dict:
    """Return current repo symbol table (builds if needed)."""
    if not repo_path:
        raise HTTPException(status_code=400, detail="repo_path required")
    symbols = _ensure_repo_symbols(repo_path)
    return {"symbols": symbols}


@app.get("/graph")
def get_graph(repo_path: str) -> dict:
    """Return repo knowledge graph (nodes + edges) for visualization."""
    if not repo_path:
        raise HTTPException(status_code=400, detail="repo_path required")
    symbols = _ensure_repo_symbols(repo_path)
    return build_repo_graph(symbols)


@app.get("/rules")
def get_rules() -> dict:
    """Return deterministic rule definitions."""
    rules_file = Path(__file__).resolve().parent / "rules" / "rules.json"
    if rules_file.exists():
        with open(rules_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"rules": []}


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
