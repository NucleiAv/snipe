/**
 * Repo Knowledge Graph panel (WebView) using a simple Mermaid-style graph.
 */

import * as vscode from "vscode";
import type { GraphResponse } from "./apiClient";

let panel: vscode.WebviewPanel | undefined;

export function openGraphPanel(
  context: vscode.ExtensionContext,
  getGraph: () => Promise<GraphResponse>
): void {
  const column = vscode.window.activeTextEditor?.viewColumn ?? vscode.ViewColumn.One;
  if (panel) {
    panel.reveal(column);
    refreshGraphContent(getGraph);
    return;
  }
  panel = vscode.window.createWebviewPanel(
    "snipeGraph",
    "Snipe Repo Knowledge Graph",
    column,
    { enableScripts: true, retainContextWhenHidden: true }
  );
  panel.onDidDispose(() => (panel = undefined));
  refreshGraphContent(getGraph);
}

async function refreshGraphContent(getGraph: () => Promise<GraphResponse>): Promise<void> {
  const p = panel;
  if (!p) return;
  try {
    const graph = await getGraph();
    p.webview.html = buildGraphHtml(graph);
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    p.webview.html = buildErrorHtml(msg);
  }
}

export function refreshGraph(getGraph: () => Promise<GraphResponse>): void {
  if (panel) refreshGraphContent(getGraph);
}

function buildGraphHtml(graph: GraphResponse): string {
  const nodes = graph.nodes || [];
  const edges = graph.edges || [];
  const nodeList = nodes.map((n) => `{ id: "${escapeJs(n.id)}", label: "${escapeJs(n.label)}", kind: "${escapeJs(n.kind)}", file: "${escapeJs(n.file_path)}", line: ${n.line} }`).join(",\n");
  const edgeList = edges.map((e) => `{ from: "${escapeJs(e.source)}", to: "${escapeJs(e.target)}", type: "${escapeJs(e.type)}" }`).join(",\n");
  return `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body { font-family: var(--vscode-font-family); padding: 12px; margin: 0; background: var(--vscode-editor-background); color: var(--vscode-editor-foreground); }
    h2 { margin-top: 0; }
    #graph { width: 100%; height: 70vh; border: 1px solid var(--vscode-panel-border); }
    .legend { margin-top: 8px; font-size: 12px; }
    .node-table { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 12px; }
    .node-table th, .node-table td { border: 1px solid var(--vscode-panel-border); padding: 6px 8px; text-align: left; }
    .node-table th { background: var(--vscode-editor-inactiveSelectionBackground); }
  </style>
</head>
<body>
  <h2>Repo Symbol Graph</h2>
  <p>Nodes: ${nodes.length}, Edges: ${edges.length}</p>
  <div id="graph"></div>
  <div class="legend">Symbols (same name across files = REFERENCES edge)</div>
  <table class="node-table">
    <thead><tr><th>Symbol</th><th>Kind</th><th>File</th><th>Line</th></tr></thead>
    <tbody>
      ${nodes.slice(0, 200).map((n) => `<tr><td>${escapeHtml(n.label)}</td><td>${escapeHtml(n.kind)}</td><td>${escapeHtml(n.file_path)}</td><td>${n.line}</td></tr>`).join("")}
      ${nodes.length > 200 ? `<tr><td colspan="4">… and ${nodes.length - 200} more</td></tr>` : ""}
    </tbody>
  </table>
  <script>
    const nodes = [${nodeList}];
    const edges = [${edgeList}];
    const el = document.getElementById("graph");
    if (nodes.length === 0) {
      el.innerHTML = "<p>No symbols in repository. Open a repo and run Snipe: Refresh Repository Symbols.</p>";
    } else {
      el.innerHTML = "<p>Graph has " + nodes.length + " nodes and " + edges.length + " edges. Table above lists symbols.</p>";
    }
  </script>
</body>
</html>`;
}

function buildErrorHtml(message: string): string {
  return `<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="font-family: var(--vscode-font-family); padding: 12px;">
  <h2>Snipe Graph</h2>
  <p style="color: var(--vscode-errorForeground);">Failed to load graph: ${escapeHtml(message)}</p>
  <p>Ensure the Snipe backend is running and the workspace folder is the repo root.</p>
</body></html>`;
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function escapeJs(s: string): string {
  return s.replace(/\\/g, "\\\\").replace(/"/g, '\\"').replace(/\n/g, "\\n");
}
