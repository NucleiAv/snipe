"""
Dynamic Repository Graph Builder.

Converts the flat symbol table produced by parser/repo_parser.py into a
two-level graph suitable for D3.js force-directed rendering:

  - FILE nodes  (one per source file)  — rendered as rounded rectangles
  - SYMBOL nodes (one per symbol)      — rendered as circle / square / diamond
  - BELONGS_TO edges                   — symbol → owning file
  - REFERENCES edges                   — same symbol name shared across files

Error highlighting:
  Diagnostics are matched to nodes by (basename, line) so that the graph
  can colour both files and individual symbols red when they contain errors.
  Full absolute paths from the diagnostic list are normalised to basenames
  because graph node paths are stored relative (e.g. "app.py" not
  "/Users/…/app.py").
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Any, Optional

from parser.symbol_extractor import extract_includes, extract_imports, extract_function_calls


def get_language(file_path: str) -> str:
    """Return a language tag for a file path based on its extension."""
    ext = file_path.split('.')[-1].lower() if '.' in file_path else ''
    if ext in ('c', 'h'):
        return 'c'
    elif ext == 'py':
        return 'python'
    return 'unknown'

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False
    nx = None


def build_repo_graph(symbols: list[dict[str, Any]], diagnostics: list[dict] = None, repo_path: str = None) -> dict[str, Any]:
    """
    Build the D3.js-compatible graph from a flat symbol list.

    Two-pass algorithm:
      1. Group symbols by file path, then emit one FILE node per file and one
         SYMBOL node per symbol, with BELONGS_TO edges connecting each symbol
         to its file.
      2. Collect every symbol label into a name_map; any label that appears in
         two or more files gets a REFERENCES edge between those occurrences so
         the viewer can spot cross-file dependencies at a glance.

    Error matching uses *basename* comparison so that diagnostics recorded with
    absolute paths (from the VSCode extension) still match graph nodes that
    store relative paths (from the repo parser).

    Args:
        symbols:     Flat list of symbol dicts from build_repo_symbol_table().
                     Each dict has at minimum: name, kind, type, file_path, line.
        diagnostics: List of diagnostic dicts saved by /analyze or
                     /save_diagnostics.  Each has: file (full path), line.

    Returns:
        {"nodes": [...], "edges": [...]} ready to be consumed by the D3.js
        force simulation in extension/webview/graph.html.
    """
    nodes = []
    edges = []
    diagnostics = diagnostics or []

    # ------------------------------------------------------------------
    # Normalise diagnostic paths to plain basenames so they can be
    # compared against graph node paths regardless of how either side
    # represents the repository root.
    # e.g. "/Users/vishva05/Desktop/snipe/demo_repo/app.py" → "app.py"
    # ------------------------------------------------------------------
    normalized_diagnostics = []
    for d in diagnostics:
        diag_file = d.get('file', '')
        normalized_diagnostics.append({
            'file': os.path.basename(diag_file),
            'line': d.get('line', 0)
        })

    # Pre-build a set of files that have *any* diagnostic error so the
    # FILE node hasErrors flag can be set in O(1) per file.
    file_errors = {d['file']: True for d in normalized_diagnostics}

    # ------------------------------------------------------------------
    # Pass 1 — Group symbols by file path (relative or absolute as stored
    # by the parser; we treat whatever the parser gives us as canonical).
    # ------------------------------------------------------------------
    files: dict[str, list[dict]] = {}
    for symbol in symbols:
        file_path = symbol.get('file_path', '')
        if file_path:
            files.setdefault(file_path, []).append(symbol)

    # ------------------------------------------------------------------
    # Pass 2 — Emit FILE nodes and SYMBOL nodes + BELONGS_TO edges.
    # ------------------------------------------------------------------
    for file_path, file_symbols in files.items():
        file_basename = os.path.basename(file_path)

        # FILE node — one rectangle per source file.
        # hasErrors drives the red fill in the D3 renderer.
        nodes.append({
            "id": f"file_{file_path}",
            "label": file_path.split('/')[-1],   # display name — basename only
            "kind": "file",
            "type": "file",
            "file_path": file_path,
            "line": 0,
            "hasErrors": file_basename in file_errors,
            "symbolCount": len(file_symbols)      # shown in node tooltip
        })

        for symbol in file_symbols:
            # Unique ID: "path:line:name" avoids collisions when the same
            # function name appears at different lines in the same file.
            symbol_id = f"{file_path}:{symbol.get('line', 0)}:{symbol.get('name', '')}"

            # A symbol has an error only when the diagnostic points to its
            # exact line — this lets us highlight individual symbols without
            # polluting every symbol in an errored file.
            symbol_has_error = any(
                d['file'] == file_basename and d['line'] == symbol.get('line')
                for d in normalized_diagnostics
            )

            # SYMBOL node — shape chosen by `kind` in the D3 renderer:
            #   function → circle, variable → square, array → diamond
            nodes.append({
                "id": symbol_id,
                "label": symbol.get('name', ''),
                "kind": symbol.get('kind', ''),    # "function" | "variable" | "array"
                "type": symbol.get('type'),         # data-type string e.g. "int", "float"
                "file_path": file_path,
                "line": symbol.get('line', 0),
                "parentFile": f"file_{file_path}",  # used by D3 layout to cluster symbols
                "hasErrors": symbol_has_error
            })

            # BELONGS_TO edge — drawn as a thin grey line in the graph.
            edges.append({
                "source": symbol_id,
                "target": f"file_{file_path}",
                "type": "BELONGS_TO"
            })

    # ------------------------------------------------------------------
    # Pass 3 — REFERENCES edges.
    # Any symbol label shared across two or more files gets cross-file
    # edges so the viewer can spot shared identifiers at a glance.
    # We only add edges between distinct occurrences (pairs, not self-loops).
    # ------------------------------------------------------------------
    name_map: dict[str, list[str]] = {}
    for node in nodes:
        if node['kind'] != 'file':
            name_map.setdefault(node['label'], []).append(node['id'])

    for ids in name_map.values():
        if len(ids) >= 2:
            # Emit one edge per ordered pair to avoid duplicate edges.
            for i, src in enumerate(ids):
                for tgt in ids[i + 1:]:
                    edges.append({
                        "source": src,
                        "target": tgt,
                        "type": "REFERENCES"
                    })

    # ------------------------------------------------------------------
    # Pass 4 — INCLUDES edges (C/H files) and IMPORTS edges (Python files).
    # Read each source file to detect #include / import statements and emit
    # new special nodes + edges so the viewer can see file-level deps.
    # ------------------------------------------------------------------
    existing_node_ids: set[str] = {n['id'] for n in nodes}

    for node in list(nodes):  # snapshot — we append inside the loop
        if node['kind'] != 'file':
            continue

        fp = node['file_path']
        # Resolve to an absolute path when repo_path is supplied.
        abs_fp = fp
        if repo_path and not os.path.isabs(fp):
            abs_fp = os.path.join(repo_path, fp)

        try:
            code = Path(abs_fp).read_text(encoding='utf-8', errors='replace')
        except OSError:
            continue

        if fp.endswith(('.c', '.h')):
            for inc in extract_includes(code, fp):
                inc_name = inc['file']
                inc_id = f'include:{inc_name}'
                if inc_id not in existing_node_ids:
                    nodes.append({
                        'id': inc_id,
                        'label': inc_name,
                        'kind': 'included_file',
                        'type': 'included_file',
                        'file_path': '',
                        'line': 0,
                        'hasErrors': False,
                        'symbolCount': 0,
                    })
                    existing_node_ids.add(inc_id)
                edges.append({
                    'source': node['id'],
                    'target': inc_id,
                    'type': 'INCLUDES',
                })

        elif fp.endswith('.py'):
            for imp in extract_imports(code, fp):
                mod_name = imp['module']
                mod_id = f'import:{mod_name}'
                if mod_id not in existing_node_ids:
                    nodes.append({
                        'id': mod_id,
                        'label': mod_name,
                        'kind': 'imported_module',
                        'type': 'imported_module',
                        'file_path': '',
                        'line': 0,
                        'hasErrors': False,
                        'symbolCount': 0,
                    })
                    existing_node_ids.add(mod_id)
                edges.append({
                    'source': node['id'],
                    'target': mod_id,
                    'type': 'IMPORTS',
                })

    # ------------------------------------------------------------------
    # Pass 5 — CALLS edges between function symbols in the same file.
    # For each file we collect its function symbols, then scan the source
    # for calls and create edges between caller and callee nodes.
    # ------------------------------------------------------------------
    # Build a map: file_path -> list of function symbol nodes
    file_func_nodes: dict[str, list[dict]] = {}
    for node in nodes:
        if node['kind'] == 'function':
            fp = node.get('file_path', '')
            file_func_nodes.setdefault(fp, []).append(node)

    for fp, func_nodes in file_func_nodes.items():
        abs_fp = fp
        if repo_path and not os.path.isabs(fp):
            abs_fp = os.path.join(repo_path, fp)
        try:
            code = Path(abs_fp).read_text(encoding='utf-8', errors='replace')
        except OSError:
            continue

        # Build symbol dicts for extract_function_calls
        sym_dicts = [{'name': n['label'], 'kind': 'function'} for n in func_nodes]
        # Build lookup: function name -> node
        func_by_name: dict[str, list[dict]] = {}
        for fn in func_nodes:
            func_by_name.setdefault(fn['label'], []).append(fn)

        calls = extract_function_calls(code, sym_dicts)
        for call in calls:
            callee_name = call['function']
            call_line = call['line']
            callee_nodes = func_by_name.get(callee_name, [])
            # Determine the caller: function whose body contains call_line.
            # Use the function defined before call_line with the closest line number.
            caller_node = None
            best_dist = float('inf')
            for fn in func_nodes:
                if fn['label'] == callee_name:
                    continue  # skip self-references
                if fn['line'] <= call_line:
                    dist = call_line - fn['line']
                    if dist < best_dist:
                        best_dist = dist
                        caller_node = fn
            if caller_node is None:
                continue
            for callee_node in callee_nodes:
                if callee_node['id'] == caller_node['id']:
                    continue
                edges.append({
                    'source': caller_node['id'],
                    'target': callee_node['id'],
                    'type': 'CALLS',
                })

    # ------------------------------------------------------------------
    # Filter out cross-language REFERENCES edges (e.g. C symbol matching
    # a Python symbol by name — these are coincidental, not real deps).
    # ------------------------------------------------------------------
    node_index = {n['id']: n for n in nodes}
    filtered_edges = []
    for edge in edges:
        if edge['type'] == 'REFERENCES':
            source_node = node_index.get(edge['source'])
            target_node = node_index.get(edge['target'])
            if source_node and target_node:
                source_lang = get_language(source_node.get('file_path', ''))
                target_lang = get_language(target_node.get('file_path', ''))
                if source_lang != target_lang:
                    continue
        filtered_edges.append(edge)

    return {"nodes": nodes, "edges": filtered_edges}


def build_graph_networkx(symbols: list[dict[str, Any]], diagnostics: list[dict] = None) -> "Optional[Any]":
    """
    Wrap build_repo_graph() output in a NetworkX DiGraph for advanced analysis
    (e.g. centrality metrics, shortest paths, cycle detection).

    This is an optional utility — the main D3.js visualisation uses
    build_repo_graph() directly.  NetworkX is not required; if it is not
    installed the function returns None rather than raising.

    Args:
        symbols:     Same symbol list as build_repo_graph().
        diagnostics: Optional diagnostics for hasErrors attributes on nodes.

    Returns:
        NetworkX DiGraph with node/edge attributes mirroring build_repo_graph(),
        or None if networkx is not installed.
    """
    if not HAS_NX:
        return None

    G = nx.DiGraph()
    graph_data = build_repo_graph(symbols, diagnostics)

    for node in graph_data["nodes"]:
        G.add_node(node["id"], **node)

    for edge in graph_data["edges"]:
        G.add_edge(edge["source"], edge["target"], type=edge["type"])

    return G
