"""
Repository knowledge graph builder.
Builds dependency and reference graph from symbol table (JSON + NetworkX).
"""
from __future__ import annotations
from pathlib import Path
from typing import Any, Optional

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False
    nx = None


def build_repo_graph(symbols: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Build a graph structure from symbol table.
    Nodes: symbols (id = file_path:line:name)
    Edges: CALLS, REFERENCES, INHERITS (simplified for MVP)
    Returns JSON-serializable dict for the extension.
    """
    nodes: list[dict] = []
    edges: list[dict] = []
    by_id: dict[str, dict] = {}

    for s in symbols:
        nid = f"{s.get('file_path', '')}:{s.get('line', 0)}:{s.get('name', '')}"
        if nid in by_id:
            continue
        node = {
            "id": nid,
            "label": s.get("name", ""),
            "kind": s.get("kind", ""),
            "type": s.get("type"),
            "file_path": s.get("file_path", ""),
            "line": s.get("line", 0),
        }
        nodes.append(node)
        by_id[nid] = node

    # Simple REFERENCES: same name across files
    name_to_ids: dict[str, list[str]] = {}
    for nid, node in by_id.items():
        name = node.get("label") or ""
        name_to_ids.setdefault(name, []).append(nid)
    for name, nids in name_to_ids.items():
        if len(nids) < 2:
            continue
        for i, a in enumerate(nids):
            for b in nids[i + 1 :]:
                edges.append({"source": a, "target": b, "type": "REFERENCES"})

    return {"nodes": nodes, "edges": edges}


def build_graph_networkx(symbols: list[dict[str, Any]]) -> "Optional[Any]":
    if not HAS_NX:
        return None
    G = nx.DiGraph()
    for s in symbols:
        nid = f"{s.get('file_path', '')}:{s.get('line', 0)}:{s.get('name', '')}"
        G.add_node(nid, **{k: v for k, v in s.items() if k != "references"})
    data = build_repo_graph(symbols)
    for e in data["edges"]:
        G.add_edge(e["source"], e["target"], type=e["type"])
    return G
