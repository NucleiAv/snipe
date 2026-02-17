/**
 * Sidebar panel provider for Snipe overview.
 */

import * as vscode from "vscode";

interface DiagnosticSummary {
  file: string;
  message: string;
  severity: string;
  line: number;
}

export class SnipeSidebarProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = "snipe-overview";

  private _view?: vscode.WebviewView;
  private _diagnostics: DiagnosticSummary[] = [];
  private _stats = {
    filesMonitored: 0,
    errors: 0,
    warnings: 0,
    symbolCount: 0,
  };

  constructor(private readonly _extensionUri: vscode.Uri) {}

  public resolveWebviewView(
    webviewView: vscode.WebviewView,
    context: vscode.WebviewViewResolveContext,
    _token: vscode.CancellationToken
  ) {
    this._view = webviewView;

    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [this._extensionUri],
    };

    webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);

    // Handle messages from the webview
    webviewView.webview.onDidReceiveMessage((data) => {
      switch (data.type) {
        case "rescanRepo":
          vscode.commands.executeCommand("snipe.refreshRepo");
          break;
        case "showGraph":
          vscode.commands.executeCommand("snipe.showGraph");
          break;
        case "searchSymbol":
          this._searchSymbol(data.query);
          break;
        case "openDiagnostic":
          this._openDiagnostic(data.file, data.line);
          break;
      }
    });
  }

  /**
   * Update sidebar with new statistics.
   */
  public updateStats(stats: {
    filesMonitored?: number;
    errors?: number;
    warnings?: number;
    symbolCount?: number;
  }): void {
    this._stats = { ...this._stats, ...stats };
    this._updateView();
  }

  /**
   * Update sidebar with new diagnostics.
   */
  public updateDiagnostics(diagnostics: DiagnosticSummary[]): void {
    // Keep only last 10
    this._diagnostics = diagnostics.slice(-10);
    this._updateView();
  }

  private _updateView(): void {
    if (this._view) {
      this._view.webview.postMessage({
        type: "update",
        stats: this._stats,
        diagnostics: this._diagnostics,
      });
    }
  }

  private _searchSymbol(query: string): void {
    // TODO: Implement symbol search
    vscode.window.showInformationMessage(`Searching for: ${query}`);
  }

  private async _openDiagnostic(file: string, line: number): Promise<void> {
    try {
      const uri = vscode.Uri.file(file);
      const document = await vscode.workspace.openTextDocument(uri);
      const editor = await vscode.window.showTextDocument(document);

      const lineNumber = Math.max(0, line - 1);
      const range = new vscode.Range(lineNumber, 0, lineNumber, 0);
      editor.selection = new vscode.Selection(range.start, range.end);
      editor.revealRange(range, vscode.TextEditorRevealType.InCenter);
    } catch (error) {
      vscode.window.showErrorMessage(`Failed to open file: ${error}`);
    }
  }

  private _getHtmlForWebview(webview: vscode.Webview): string {
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Snipe Overview</title>
  <style>
    body {
      padding: 10px;
      color: var(--vscode-foreground);
      font-family: var(--vscode-font-family);
      font-size: var(--vscode-font-size);
    }

    h2 {
      font-size: 14px;
      font-weight: 600;
      margin: 16px 0 8px 0;
      color: var(--vscode-foreground);
    }

    .stats-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
      margin-bottom: 16px;
    }

    .stat-card {
      background: var(--vscode-editor-inactiveSelectionBackground);
      padding: 12px;
      border-radius: 4px;
      border: 1px solid var(--vscode-panel-border);
    }

    .stat-value {
      font-size: 24px;
      font-weight: bold;
      color: var(--vscode-foreground);
    }

    .stat-label {
      font-size: 11px;
      color: var(--vscode-descriptionForeground);
      margin-top: 4px;
    }

    .stat-card.errors .stat-value {
      color: var(--vscode-errorForeground);
    }

    .stat-card.warnings .stat-value {
      color: var(--vscode-editorWarning-foreground);
    }

    .button-group {
      display: flex;
      flex-direction: column;
      gap: 8px;
      margin-bottom: 16px;
    }

    button {
      background: var(--vscode-button-background);
      color: var(--vscode-button-foreground);
      border: none;
      padding: 8px 12px;
      border-radius: 2px;
      cursor: pointer;
      font-size: 13px;
      text-align: left;
    }

    button:hover {
      background: var(--vscode-button-hoverBackground);
    }

    button:active {
      background: var(--vscode-button-activeBackground);
    }

    .secondary-button {
      background: var(--vscode-button-secondaryBackground);
      color: var(--vscode-button-secondaryForeground);
    }

    .secondary-button:hover {
      background: var(--vscode-button-secondaryHoverBackground);
    }

    .search-box {
      width: 100%;
      padding: 6px 8px;
      background: var(--vscode-input-background);
      color: var(--vscode-input-foreground);
      border: 1px solid var(--vscode-input-border);
      border-radius: 2px;
      font-size: 13px;
      box-sizing: border-box;
    }

    .search-box:focus {
      outline: 1px solid var(--vscode-focusBorder);
    }

    .diagnostic-list {
      list-style: none;
      padding: 0;
      margin: 0;
    }

    .diagnostic-item {
      padding: 8px;
      margin-bottom: 4px;
      background: var(--vscode-editor-inactiveSelectionBackground);
      border-left: 3px solid var(--vscode-editorWarning-foreground);
      cursor: pointer;
      border-radius: 2px;
      font-size: 12px;
    }

    .diagnostic-item:hover {
      background: var(--vscode-list-hoverBackground);
    }

    .diagnostic-item.error {
      border-left-color: var(--vscode-errorForeground);
    }

    .diagnostic-file {
      font-size: 11px;
      color: var(--vscode-descriptionForeground);
      margin-bottom: 4px;
    }

    .diagnostic-message {
      color: var(--vscode-foreground);
    }

    .empty-state {
      text-align: center;
      padding: 32px 16px;
      color: var(--vscode-descriptionForeground);
      font-size: 12px;
    }

    .icon {
      margin-right: 6px;
    }
  </style>
</head>
<body>
  <h2>📊 Analysis Status</h2>
  <div class="stats-grid">
    <div class="stat-card">
      <div class="stat-value" id="filesMonitored">0</div>
      <div class="stat-label">Files Monitored</div>
    </div>
    <div class="stat-card">
      <div class="stat-value" id="symbolCount">0</div>
      <div class="stat-label">Symbols</div>
    </div>
    <div class="stat-card errors">
      <div class="stat-value" id="errors">0</div>
      <div class="stat-label">Errors</div>
    </div>
    <div class="stat-card warnings">
      <div class="stat-value" id="warnings">0</div>
      <div class="stat-label">Warnings</div>
    </div>
  </div>

  <h2>⚡ Quick Actions</h2>
  <div class="button-group">
    <button onclick="rescanRepo()">
      <span class="icon">🔄</span> Re-scan Repository
    </button>
    <button onclick="showGraph()" class="secondary-button">
      <span class="icon">📊</span> Show Graph
    </button>
  </div>

  <h2>🔍 Symbol Search</h2>
  <input
    type="text"
    class="search-box"
    placeholder="Search symbols..."
    id="searchInput"
    onkeypress="handleSearch(event)"
  />

  <h2>⚠️ Recent Warnings</h2>
  <ul class="diagnostic-list" id="diagnosticList">
    <li class="empty-state">No warnings yet</li>
  </ul>

  <script>
    const vscode = acquireVsCodeApi();

    function rescanRepo() {
      vscode.postMessage({ type: 'rescanRepo' });
    }

    function showGraph() {
      vscode.postMessage({ type: 'showGraph' });
    }

    function handleSearch(event) {
      if (event.key === 'Enter') {
        const query = event.target.value;
        if (query) {
          vscode.postMessage({ type: 'searchSymbol', query });
        }
      }
    }

    function openDiagnostic(file, line) {
      vscode.postMessage({ type: 'openDiagnostic', file, line });
    }

    // Listen for updates from extension
    window.addEventListener('message', event => {
      const message = event.data;

      if (message.type === 'update') {
        updateStats(message.stats);
        updateDiagnostics(message.diagnostics);
      }
    });

    function updateStats(stats) {
      document.getElementById('filesMonitored').textContent = stats.filesMonitored || 0;
      document.getElementById('symbolCount').textContent = stats.symbolCount || 0;
      document.getElementById('errors').textContent = stats.errors || 0;
      document.getElementById('warnings').textContent = stats.warnings || 0;
    }

    function updateDiagnostics(diagnostics) {
      const list = document.getElementById('diagnosticList');

      if (!diagnostics || diagnostics.length === 0) {
        list.innerHTML = '<li class="empty-state">No warnings yet</li>';
        return;
      }

      list.innerHTML = diagnostics.map(d => {
        const severityClass = d.severity === 'error' ? 'error' : '';
        const fileName = d.file.split('/').pop();
        return \`
          <li class="diagnostic-item \${severityClass}" onclick="openDiagnostic('\${d.file}', \${d.line})">
            <div class="diagnostic-file">\${fileName}:\${d.line}</div>
            <div class="diagnostic-message">\${d.message}</div>
          </li>
        \`;
      }).join('');
    }
  </script>
</body>
</html>`;
  }
}
