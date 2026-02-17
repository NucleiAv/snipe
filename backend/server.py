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
from graph.graph_builder import build_d3_graph
from explainer import get_explainer


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


class ExplainRequest(BaseModel):
    diagnostic: dict
    code_context: str


class FixRequest(BaseModel):
    diagnostic: dict
    code: str


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

    # Save diagnostics to file for graph error highlighting
    snipe_dir = Path(repo_path) / ".snipe"
    snipe_dir.mkdir(exist_ok=True)

    diagnostics_file = snipe_dir / "diagnostics.json"
    diagnostics_dict = [_diagnostic_to_dict(d) for d in diagnostics]
    with open(diagnostics_file, 'w') as f:
        json.dump(diagnostics_dict, f, indent=2)

    return {
        "diagnostics": diagnostics_dict,
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


@app.post("/save_diagnostics")
def save_diagnostics(data: dict) -> dict:
    """Save combined diagnostics from all open files for graph error highlighting."""
    repo_path = data.get('repo_path', '')
    diagnostics = data.get('diagnostics', [])

    if not repo_path or not Path(repo_path).is_dir():
        raise HTTPException(status_code=400, detail="Invalid repo_path")

    snipe_dir = Path(repo_path) / ".snipe"
    snipe_dir.mkdir(exist_ok=True)

    diagnostics_file = snipe_dir / "diagnostics.json"
    with open(diagnostics_file, 'w') as f:
        json.dump(diagnostics, f, indent=2)

    log.info("Saved %d diagnostics to %s", len(diagnostics), diagnostics_file)
    return {"saved": len(diagnostics)}


@app.get("/symbols")
def get_symbols(repo_path: str) -> dict:
    """Return current repo symbol table (builds if needed)."""
    if not repo_path:
        raise HTTPException(status_code=400, detail="repo_path required")
    symbols = _ensure_repo_symbols(repo_path)
    return {"symbols": symbols}


@app.get("/graph")
def get_graph(repo_path: str) -> dict:
    """
    Return dynamic repo knowledge graph (nodes + edges) for visualization.
    Updates in real-time with error highlighting.
    """
    if not repo_path:
        raise HTTPException(status_code=400, detail="repo_path required")

    # Get current symbols
    symbols = _ensure_repo_symbols(repo_path)

    # Get current diagnostics for error highlighting
    diagnostics = []
    diagnostics_file = Path(repo_path) / ".snipe" / "diagnostics.json"
    if diagnostics_file.exists():
        try:
            diagnostics_text = diagnostics_file.read_text()
            diagnostics = json.loads(diagnostics_text)
        except Exception as e:
            log.warning(f"Failed to load diagnostics: {e}")

    # Build dynamic graph with error highlighting
    graph_data = build_repo_graph(symbols, diagnostics)

    return graph_data


@app.post("/explain")
def explain_diagnostic(request: ExplainRequest) -> dict:
    """
    Generate AI-powered explanation for a diagnostic.
    Uses Google Gemini to provide clear, actionable explanations.
    """
    explainer = get_explainer()

    if not explainer.is_available():
        return {
            "explanation": None,
            "error": "AI explanations not available. Check GOOGLE_API_KEY environment variable."
        }

    try:
        explanation = explainer.explain_diagnostic(
            request.diagnostic,
            request.code_context
        )

        if explanation:
            return {"explanation": explanation}
        else:
            return {
                "explanation": None,
                "error": "Failed to generate explanation"
            }
    except Exception as e:
        log.error(f"Error in /explain endpoint: {e}")
        return {
            "explanation": None,
            "error": str(e)
        }


@app.post("/fix")
def fix_code(request: FixRequest) -> dict:
    """
    Generate AI-powered code fix for a diagnostic.
    Uses Claude Sonnet 4 to generate fixed code with explanation.
    """
    fixer = get_fixer()

    if not fixer.is_available():
        return {
            "fixed_code": None,
            "explanation": None,
            "error": "AI code fixes not available. Check ANTHROPIC_API_KEY environment variable."
        }

    try:
        result = fixer.generate_fix(
            request.diagnostic,
            request.code
        )

        if result:
            return {
                "fixed_code": result.get("fixed_code"),
                "explanation": result.get("explanation"),
                "error": None
            }
        else:
            return {
                "fixed_code": None,
                "explanation": None,
                "error": "Failed to generate code fix"
            }
    except Exception as e:
        log.error(f"Error in /fix endpoint: {e}")
        return {
            "fixed_code": None,
            "explanation": None,
            "error": str(e)
        }


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
