# Snipe Graph Visualisation Feature

Interactive D3.js force-directed graph that shows every file and symbol in the
repository as a node, draws relationships between them as edges, and highlights
any node that has an active diagnostic error in red.

---

## Overview

The graph gives developers a bird's-eye view of their codebase:

- **File nodes** (rounded rectangles) — one per source file
- **Symbol nodes** — one per function, variable, or array inside each file
- **BELONGS_TO edges** — connect each symbol to its file
- **REFERENCES edges** — connect symbols that share the same name across files
- **Error highlighting** — any node with an active Snipe diagnostic turns red

Click any node to jump directly to that file and line in the VS Code editor.

---

## Architecture

```
VS Code Extension (TypeScript)
│
├── extension.ts            ← registers "snipe.showGraph" command,
│                              wires up auto-refresh listeners
│
├── graphPanel.ts           ← WebviewPanel lifecycle manager
│   │   createOrShow()         creates / reveals the panel
│   │   refresh()              re-fetches data from backend
│   │   sendGraphData()        POSTs data to webview via message passing
│   └── openFileAtLine()       handles click-to-navigate
│
└── webview/graph.html      ← D3.js force simulation + legend + UI
        receives "graphData" message
        renders nodes/edges
        sends "openFile" messages back

                    ▼  HTTP GET /graph?repo_path=…
Backend (Python / FastAPI)
│
├── server.py               ← /graph endpoint
│
└── graph/repo_graph.py     ← build_repo_graph()
        reads symbol table
        normalises diagnostic paths
        emits nodes + edges JSON
```

---

## New Files Created

| File | Purpose |
|------|---------|
| `backend/graph/repo_graph.py` | Core graph builder — converts symbol table to D3-compatible nodes/edges |
| `extension/src/graphPanel.ts` | VS Code WebviewPanel wrapper, message passing, click-to-navigate |
| `extension/webview/graph.html` | D3.js v7 force simulation, node rendering, legend, error highlighting |

---

## How It Works — Step by Step

### 1. Symbols → Graph Nodes (backend/graph/repo_graph.py)

```
build_repo_graph(symbols, diagnostics)
  │
  ├─ Group symbols by file_path
  │
  ├─ For each file:
  │     emit FILE node   { id, label, kind:"file", hasErrors }
  │     For each symbol:
  │       emit SYMBOL node { id, label, kind, type, line, hasErrors }
  │       emit BELONGS_TO edge { source: symbol, target: file }
  │
  └─ Collect name_map; any label in 2+ files → REFERENCES edges
```

`hasErrors` is set by comparing the diagnostic's `file` (basename) and `line`
against each node.  Full absolute paths from the extension are normalised to
basenames to prevent path-format mismatches.

### 2. D3.js Rendering (extension/webview/graph.html)

```
window.onmessage "graphData"
  │
  ├─ d3.forceSimulation(nodes)
  │     .force("link",    d3.forceLink — BELONGS_TO edges)
  │     .force("charge",  d3.forceManyBody — repulsion)
  │     .force("center",  d3.forceCenter — keep graph centered)
  │     .force("collide", d3.forceCollide — prevent overlap)
  │
  └─ nodeGroup.each(d => …)
        d.kind === "file"     → <rect rx=8>     brown / red
        d.kind === "function" → <circle>        blue  / red
        d.kind === "variable" → <rect>          green / red
        d.kind === "array"    → <rect rotate45> orange/ red
```

Node shape is determined by `d.kind` (not `d.type` — a common confusion since
the parser also stores the data type, e.g. "int", in `d.type`).

### 3. Error Highlighting

```
Backend /analyze endpoint:
  → runs type/bounds/signature checks
  → saves results to <repo>/.snipe/diagnostics.json  (per-file)

Extension analyzeAllOpenFiles():
  → on every analysis cycle, re-analyzes ALL open files
  → merges results into allDiagnosticsMap (keyed by absolute file path)
  → POSTs combined list to /save_diagnostics

/graph endpoint:
  → loads .snipe/diagnostics.json
  → passes to build_repo_graph(symbols, diagnostics)
  → hasErrors=true on any node whose (basename, line) matches a diagnostic

D3 renderer:
  → d.hasErrors ? fill="#ff0000" : fill=<normal colour>
```

Red = error.  No other node ever renders red.

### 4. Click-to-Navigate

```
User clicks node in webview
  │
  └─ vscode.postMessage({ type:"openFile", file: absolutePath, line: N })
       │
       └─ graphPanel.ts openFileAtLine(path, line)
             vscode.workspace.openTextDocument(uri)
             editor.revealRange(range, InCenter)
```

- **File nodes** open at line 1 (beginning of file).
- **Symbol nodes** open at the exact source line of the symbol definition.
- `workspacePath` is sent alongside graph data so the webview can prepend it
  to relative `file_path` values before posting the message.

### 5. Live Updates

| Trigger | What Happens |
|---------|-------------|
| Keystroke (debounced 300 ms) | `runAnalysis()` → diagnostics updated → graph refreshes after 1 s |
| File save | `/refresh` re-scans repo symbols → graph refreshes after 1.5 s |
| File switch | `/refresh` re-scans → `debouncedAnalysis()` on new file → graph refreshes after 1.5 s |
| File created/deleted | `/refresh` re-scans → graph refreshes after 0.5 s |

All graph refreshes call `GraphPanel.refresh()` which calls `sendGraphData()` —
a lightweight re-fetch that does **not** rebuild the WebviewPanel HTML.

---

## API Endpoints Added

### GET /graph

Returns the complete graph for a repository.

**Query params:** `repo_path` (string, required)

**Response:**
```json
{
  "nodes": [
    {
      "id": "file_app.py",
      "label": "app.py",
      "kind": "file",
      "file_path": "app.py",
      "line": 0,
      "hasErrors": false,
      "symbolCount": 4
    },
    {
      "id": "app.py:10:calculate",
      "label": "calculate",
      "kind": "function",
      "type": null,
      "file_path": "app.py",
      "line": 10,
      "parentFile": "file_app.py",
      "hasErrors": true
    }
  ],
  "edges": [
    { "source": "app.py:10:calculate", "target": "file_app.py", "type": "BELONGS_TO" }
  ]
}
```

### POST /save_diagnostics

Saves combined diagnostics from all open files so the graph can show errors
across the entire repository, not just the active file.

**Body:**
```json
{ "repo_path": "/absolute/path/to/repo", "diagnostics": [...] }
```

**Response:** `{ "saved": 5 }`

---

## Configuration

No configuration is required.  The graph reads from the same backend server
(default port 8765) that the rest of Snipe uses.

To open the graph: **Command Palette → "Snipe: Show Repository Graph"**

---

## How to Test

1. Start the backend:
   ```bash
   cd backend
   uvicorn server:app --reload --port 8765
   ```

2. Open a supported file (`.py`, `.c`, `.h`) in VS Code.

3. Run **Snipe: Refresh Repository** to scan symbols.

4. Run **Snipe: Show Repository Graph** — the graph panel opens.

5. Introduce an error in a file and save — watch the corresponding node turn red.

6. Click any node — the editor jumps to that file and line.

---

## Known Limitations

- **Supported languages:** Python (`.py`) and C (`.c`, `.h`) only.  The parser
  does not yet handle TypeScript, JavaScript, or other languages.

- **REFERENCES edges** are name-based heuristics, not true call-graph analysis.
  Two functions with the same name in different files will be linked even if
  they are unrelated.

- **Performance:** Very large repositories (thousands of files) may produce a
  dense graph that is hard to read.  The D3 force simulation handles up to a
  few hundred nodes comfortably.

- **Error persistence:** `allDiagnosticsMap` is in-memory and resets when the
  extension host restarts (e.g. after a VS Code reload).

- **Path handling:** The graph uses basenames for error matching, so two files
  with the same name in different directories will share error highlighting.
