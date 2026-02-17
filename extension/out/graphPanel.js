"use strict";
/**
 * GraphPanel — VS Code WebviewPanel wrapper for the D3.js repository graph.
 *
 * Responsibilities:
 *   - Create (or reveal) a VS Code WebviewPanel that hosts graph.html.
 *   - Fetch graph data from the Snipe backend (/graph endpoint) and post it
 *     to the webview via message passing.
 *   - Handle "openFile" messages from the webview so clicking a node jumps
 *     the editor to that file/line.
 *   - Expose a refresh() method so other parts of the extension can trigger
 *     a data reload without rebuilding the panel from scratch.
 *
 * Singleton pattern:
 *   Only one GraphPanel can exist at a time (stored in `currentPanel`).
 *   createOrShow() reuses the existing panel if it is already open.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.GraphPanel = void 0;
exports.refreshGraph = refreshGraph;
exports.getCurrentPanel = getCurrentPanel;
const vscode = require("vscode");
const path = require("path");
const fs = require("fs");
// Module-level singleton — avoids creating duplicate panels.
let currentPanel;
class GraphPanel {
    // ---------------------------------------------------------------------------
    // Static factory methods
    // ---------------------------------------------------------------------------
    /**
     * Create a new graph panel or bring the existing one to the foreground.
     *
     * @param extensionPath  Absolute path to the extension root (used to load
     *                       graph.html from the webview/ subdirectory).
     * @param graphDataFetcher  Async callback that returns the latest graph data
     *                          from the backend.  Called on every refresh.
     */
    static createOrShow(extensionPath, graphDataFetcher) {
        const column = vscode.window.activeTextEditor
            ? vscode.window.activeTextEditor.viewColumn
            : vscode.ViewColumn.One;
        if (currentPanel) {
            // Panel already exists — just reveal it and refresh the data.
            currentPanel.panel.reveal(column);
            currentPanel.update(graphDataFetcher);
            return;
        }
        // Create a brand-new WebviewPanel.
        const panel = vscode.window.createWebviewPanel(GraphPanel.viewType, "Snipe: Repository Graph", column || vscode.ViewColumn.One, {
            enableScripts: true, // required for D3.js
            retainContextWhenHidden: true, // keep the simulation running while the tab is hidden
            localResourceRoots: [vscode.Uri.file(path.join(extensionPath, "webview"))],
        });
        currentPanel = new GraphPanel(panel, extensionPath, graphDataFetcher);
    }
    /**
     * Revive a serialised panel after VS Code restarts.
     * VS Code calls this when the user had a graph panel open and reloads the window.
     */
    static revive(panel, extensionPath, graphDataFetcher) {
        currentPanel = new GraphPanel(panel, extensionPath, graphDataFetcher);
    }
    // ---------------------------------------------------------------------------
    // Constructor — private; use createOrShow() or revive() instead.
    // ---------------------------------------------------------------------------
    constructor(panel, extensionPath, graphDataFetcher) {
        this.graphDataFetcher = graphDataFetcher;
        this.disposables = [];
        this.panel = panel;
        this.extensionPath = extensionPath;
        // Render the initial HTML (the webview sends "ready" once scripts execute).
        this.update(graphDataFetcher);
        // Clean up when the user closes the panel tab.
        this.panel.onDidDispose(() => this.dispose(), null, this.disposables);
        // Handle messages posted from graph.html via vscode.postMessage().
        this.panel.webview.onDidReceiveMessage(async (message) => {
            switch (message.type) {
                case "ready":
                    // The webview's DOMContentLoaded fired — safe to send graph data.
                    await this.sendGraphData();
                    break;
                case "openFile":
                    // User clicked a graph node — jump editor to that file and line.
                    await this.openFileAtLine(message.file, message.line);
                    break;
                default:
                    console.warn("Unknown message type from graph webview:", message.type);
            }
        }, null, this.disposables);
    }
    // ---------------------------------------------------------------------------
    // Public methods
    // ---------------------------------------------------------------------------
    /**
     * Replace the data fetcher callback and re-render the HTML.
     * Called when the panel is revealed with a potentially different repo path.
     */
    async update(graphDataFetcher) {
        if (graphDataFetcher) {
            this.graphDataFetcher = graphDataFetcher;
        }
        // Re-inject the HTML; the webview will fire "ready" once it loads,
        // triggering sendGraphData() automatically.
        this.panel.webview.html = this.getHtmlForWebview();
    }
    /**
     * Re-fetch graph data from the backend and push it to the webview.
     * Called by extension.ts after file save, file switch, or text changes.
     */
    async refresh() {
        console.log("GraphPanel: refreshing graph data…");
        await this.sendGraphData();
        console.log("GraphPanel: graph data refreshed");
    }
    dispose() {
        currentPanel = undefined;
        this.panel.dispose();
        while (this.disposables.length) {
            const d = this.disposables.pop();
            if (d)
                d.dispose();
        }
    }
    // ---------------------------------------------------------------------------
    // Private helpers
    // ---------------------------------------------------------------------------
    /**
     * Call the graphDataFetcher, then post the result to the webview.
     * Also sends the workspace root path so the webview can resolve relative
     * file_path values to absolute paths for click-to-navigate.
     */
    async sendGraphData() {
        try {
            const graphData = await this.graphDataFetcher();
            const workspacePath = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
            this.panel.webview.postMessage({
                type: "graphData",
                data: graphData,
                workspacePath,
            });
        }
        catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            this.panel.webview.postMessage({
                type: "error",
                message: `Failed to load graph: ${message}`,
            });
        }
    }
    /**
     * Open a file in the main editor column and scroll to the target line.
     * Line numbers are 1-based (matching source files); the VS Code API is
     * 0-based, so we subtract 1.
     */
    async openFileAtLine(filePath, line) {
        try {
            // Strip "file://" prefix that can appear in webview message payloads.
            const cleanPath = filePath.startsWith("file:") ? filePath.substring(5) : filePath;
            const uri = vscode.Uri.file(cleanPath);
            const document = await vscode.workspace.openTextDocument(uri);
            const editor = await vscode.window.showTextDocument(document, {
                viewColumn: vscode.ViewColumn.One,
            });
            const lineNumber = Math.max(0, line - 1); // convert 1-based → 0-based
            const range = new vscode.Range(lineNumber, 0, lineNumber, 0);
            editor.selection = new vscode.Selection(range.start, range.end);
            editor.revealRange(range, vscode.TextEditorRevealType.InCenter);
        }
        catch (error) {
            vscode.window.showErrorMessage(`Snipe: Failed to open file: ${error instanceof Error ? error.message : String(error)}`);
        }
    }
    /**
     * Read graph.html from disk and inject a Content Security Policy header.
     *
     * We read from disk (rather than inlining) so the HTML can be edited
     * independently and hot-reloaded during development.
     *
     * CSP allows:
     *   - D3.js loaded from d3js.org CDN
     *   - Inline <script> blocks (required by D3 idioms)
     *   - Inline <style> blocks
     */
    getHtmlForWebview() {
        const htmlPath = path.join(this.extensionPath, "webview", "graph.html");
        try {
            let html = fs.readFileSync(htmlPath, "utf8");
            const cspMeta = `
        <meta http-equiv="Content-Security-Policy"
          content="default-src 'none';
                   script-src https://d3js.org 'unsafe-inline';
                   style-src 'unsafe-inline';
                   img-src vscode-resource: https:;">
      `;
            html = html.replace("<head>", `<head>\n${cspMeta}`);
            return html;
        }
        catch (error) {
            return this.getErrorHtml(`Failed to load graph.html: ${error instanceof Error ? error.message : String(error)}`);
        }
    }
    /** Fallback HTML rendered when graph.html cannot be read. */
    getErrorHtml(message) {
        return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Error</title>
  <style>
    body { margin: 0; padding: 20px; background: #1e1e1e; color: #ccc;
           font-family: var(--vscode-font-family, 'Segoe UI', sans-serif); }
    .error { color: #f48771; padding: 20px; border: 1px solid #f48771;
             border-radius: 5px; background: rgba(244,135,113,.1); }
  </style>
</head>
<body>
  <div class="error">
    <h2>Error Loading Graph</h2>
    <p>${this.escapeHtml(message)}</p>
  </div>
</body>
</html>`;
    }
    escapeHtml(text) {
        return text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
}
exports.GraphPanel = GraphPanel;
GraphPanel.viewType = "snipeGraph";
// ---------------------------------------------------------------------------
// Module-level helpers used by extension.ts
// ---------------------------------------------------------------------------
/** Trigger a data refresh on the currently open panel (no-op if none). */
function refreshGraph(graphDataFetcher) {
    if (currentPanel) {
        currentPanel.update(graphDataFetcher);
    }
}
/** Return the active GraphPanel instance, or undefined if none is open. */
function getCurrentPanel() {
    return currentPanel;
}
//# sourceMappingURL=graphPanel.js.map