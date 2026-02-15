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


class AnalyzeRequest(BaseModel):
    content: str
    file_path: str
    repo_path: str
    language: Optional[str] = None


class RefreshRequest(BaseModel):
    repo_path: str


def _ensure_repo_symbols(repo_path: str) -> list[dict]:
    global _repo_symbols, _repo_path
    if _repo_path != repo_path or not _repo_symbols:
        _repo_path = repo_path
        _symbols_path.parent.mkdir(parents=True, exist_ok=True)
        _repo_symbols = build_repo_symbol_table(repo_path, output_json_path=_symbols_path)
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
    diagnostics.extend(check_type_mismatch(buffer_refs, buffer_symbols, repo_dicts, current_file))
    diagnostics.extend(check_array_bounds(buffer_refs, buffer_symbols, repo_dicts, current_file))
    diagnostics.extend(check_function_signatures(buffer_refs, repo_dicts, current_file))
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
