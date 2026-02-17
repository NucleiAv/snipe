/**
 * extension.ts — Snipe VS Code Extension entry point.
 *
 * Lifecycle:
 *   activate()   → registers all commands, event listeners, and UI components.
 *   deactivate() → clears debounce timers on extension shutdown.
 *
 * Key responsibilities:
 *   1. ANALYSIS  — On every keystroke (debounced 300 ms) and on file switch,
 *      send the active buffer to the backend /analyze endpoint and display
 *      the returned diagnostics as VS Code squiggle decorations.
 *
 *   2. GRAPH     — Open a D3.js force-directed graph (GraphPanel) via the
 *      "snipe.showGraph" command.  The graph auto-refreshes on save, on file
 *      switch, and one second after the user stops typing.
 *
 *   3. DIAGNOSTICS MAP — allDiagnosticsMap persists per-file diagnostics
 *      across file switches so the graph always shows errors for ALL open
 *      files, not just the currently focused one.
 *
 *   4. SIDEBAR / STATUS BAR — Surface error/warning counts in the Snipe
 *      activity-bar sidebar and status-bar item.
 *
 * Backend communication is handled by apiClient.ts (HTTP fetch to localhost:8765).
 */

import * as vscode from "vscode";
import { analyzeBuffer, getGraph, refreshRepo, healthCheck, OpenBuffer } from "./apiClient";
import { setDiagnostics, clearDiagnostics } from "./diagnostics";
import { GraphPanel, getCurrentPanel } from "./graphPanel";
import { SnipeStatusBar } from "./statusBar";
import { SnipeSidebarProvider } from "./sidebarProvider";

const DIAGNOSTIC_COLLECTION = "snipe";
const DEFAULT_PORT = 8765;
const DEBOUNCE_MS = 300;

let diagnosticCollection: vscode.DiagnosticCollection;
let debounceTimer: NodeJS.Timeout | undefined;
let graphRefreshTimeout: NodeJS.Timeout | undefined;
let statusBar: SnipeStatusBar;
let sidebarProvider: SnipeSidebarProvider;
let currentGraphPanel: GraphPanel | undefined;

// Persistent map of per-file diagnostics so switching files never discards previous results.
// key = absolute file path, value = diagnostics array from last analysis of that file.
const allDiagnosticsMap: Map<string, any[]> = new Map();

export function activate(context: vscode.ExtensionContext): void {
  diagnosticCollection = vscode.languages.createDiagnosticCollection(DIAGNOSTIC_COLLECTION);
  context.subscriptions.push(diagnosticCollection);

  // Create status bar
  statusBar = new SnipeStatusBar();
  context.subscriptions.push(statusBar);

  // Register sidebar provider
  sidebarProvider = new SnipeSidebarProvider(context.extensionUri);
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(
      SnipeSidebarProvider.viewType,
      sidebarProvider
    )
  );

  const runAnalysis = (doc: vscode.TextDocument) => {
    if (!isSupported(doc)) return;
    const repoPath = getRepoPath();
    if (!repoPath) return;

    // Collect unsaved content from other open supported files so the server
    // can use live (not stale on-disk) symbols for cross-file checks.
    const openBuffers: OpenBuffer[] = [];
    for (const otherDoc of vscode.workspace.textDocuments) {
      if (otherDoc.uri.toString() === doc.uri.toString()) continue;
      if (!isSupported(otherDoc)) continue;
      if (otherDoc.isClosed) continue;
      openBuffers.push({ content: otherDoc.getText(), file_path: otherDoc.uri.fsPath });
    }

    clearDiagnostics(doc.uri, diagnosticCollection);
    analyzeBuffer({
      content: doc.getText(),
      file_path: doc.uri.fsPath,
      repo_path: repoPath,
      open_buffers: openBuffers.length > 0 ? openBuffers : undefined,
    })
      .then((res) => {
        setDiagnostics(doc.uri, res.diagnostics, diagnosticCollection);

        // Update sidebar
        const errors = res.diagnostics.filter(d => d.severity === "error").length;
        const warnings = res.diagnostics.filter(d => d.severity === "warning").length;

        sidebarProvider.updateStats({ errors, warnings });
        sidebarProvider.updateDiagnostics(
          res.diagnostics.map(d => ({
            file: d.file,
            message: d.message,
            severity: d.severity,
            line: d.line,
          }))
        );

        // Update the persistent map with fresh results for this file
        allDiagnosticsMap.set(doc.uri.fsPath, res.diagnostics);

        // Persist the combined map (all files) so the graph highlights every error
        analyzeAllOpenFiles(repoPath).catch(() => {
          // Silently fail – graph error highlighting is best-effort
        });
      })
      .catch(() => {
        // Backend not running or error – leave diagnostics clear or show status
      });
  };

  const debouncedAnalysis = (doc: vscode.TextDocument) => {
    if (debounceTimer) clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => runAnalysis(doc), DEBOUNCE_MS);
  };

  context.subscriptions.push(
    vscode.workspace.onDidChangeTextDocument((e) => {
      if (e.document === vscode.window.activeTextEditor?.document && isSupported(e.document)) {
        debouncedAnalysis(e.document);

        // Clear previous graph refresh timeout
        if (graphRefreshTimeout) {
          clearTimeout(graphRefreshTimeout);
        }

        // Refresh graph 1 second after typing stops
        graphRefreshTimeout = setTimeout(() => {
          const panel = getCurrentPanel();
          if (panel) {
            console.log('Auto-refreshing graph after text change...');
            panel.refresh();
          }
        }, 1000);
      }
    })
  );

  context.subscriptions.push(
    vscode.workspace.onDidOpenTextDocument((doc) => {
      if (doc === vscode.window.activeTextEditor?.document && isSupported(doc)) {
        debouncedAnalysis(doc);
      }
    })
  );

  context.subscriptions.push(
    vscode.window.onDidChangeActiveTextEditor(async (editor) => {
      if (editor && isSupported(editor.document)) {
        const repoPath = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
        if (!repoPath) return;

        console.log('File switched, refreshing repo symbols...');

        // Refresh repo symbols so the new file's symbols are up-to-date
        try {
          await refreshRepo(repoPath, DEFAULT_PORT);
        } catch (error) {
          console.error('Failed to refresh repo on file switch:', error);
        }

        // Run analysis on the newly active file
        debouncedAnalysis(editor.document);

        // Refresh graph after analysis has time to complete
        setTimeout(() => {
          const panel = getCurrentPanel();
          if (panel) panel.refresh();
        }, 1500);
      }
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("snipe.refreshRepo", async () => {
      const repoPath = getRepoPath();
      if (!repoPath) {
        vscode.window.showWarningMessage("Snipe: Open a workspace folder (repo root) first.");
        return;
      }
      const ok = await healthCheck(DEFAULT_PORT);
      if (!ok) {
        vscode.window.showErrorMessage("Snipe: Backend not running. Start it with: cd backend && uvicorn server:app --reload --port 8765");
        return;
      }
      try {
        const res = await refreshRepo(repoPath, DEFAULT_PORT);
        vscode.window.showInformationMessage(`Snipe: Refreshed ${res.symbol_count} symbols.`);

        // Analyze all open supported docs so cross-file diagnostics show
        for (const doc of vscode.workspace.textDocuments) {
          if (isSupported(doc)) runAnalysis(doc);
        }

        // Update sidebar with symbol count
        sidebarProvider.updateStats({ symbolCount: res.symbol_count });

        // Refresh graph if open
        if (currentGraphPanel) {
          currentGraphPanel.refresh();
        }

      } catch (e) {
        vscode.window.showErrorMessage("Snipe: Refresh failed. " + (e instanceof Error ? e.message : String(e)));
      }
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("snipe.showGraph", () => {
      const repoPath = getRepoPath();
      if (!repoPath) {
        vscode.window.showWarningMessage("Snipe: Open a workspace folder (repo root) first.");
        return;
      }
      GraphPanel.createOrShow(context.extensionPath, async () => {
        const graph = await getGraph(repoPath, DEFAULT_PORT);
        return {
          nodes: graph.nodes.map(n => ({ ...n, file: n.file_path })),
          links: graph.edges.map(e => ({ source: e.source, target: e.target, relationship: e.type }))
        };
      });

      // Store reference to current panel
      currentGraphPanel = getCurrentPanel();
    })
  );

  // Analyze all open supported docs on startup so cross-file diagnostics show
  const repoPath = getRepoPath();
  if (repoPath) {
    for (const doc of vscode.workspace.textDocuments) {
      if (isSupported(doc)) runAnalysis(doc);
    }
  }

  // Watch for file creation - refresh repo and graph
  context.subscriptions.push(
    vscode.workspace.onDidCreateFiles(async (e) => {
      const repoPath = getRepoPath();
      if (!repoPath) return;

      try {
        await refreshRepo(repoPath, DEFAULT_PORT);
        if (currentGraphPanel) {
          setTimeout(() => currentGraphPanel?.refresh(), 500);
        }
      } catch (error) {
        // Silently fail if backend not running
      }
    })
  );

  // Watch for file deletion - refresh repo and graph
  context.subscriptions.push(
    vscode.workspace.onDidDeleteFiles(async (e) => {
      const repoPath = getRepoPath();
      if (!repoPath) return;

      try {
        await refreshRepo(repoPath, DEFAULT_PORT);
        if (currentGraphPanel) {
          setTimeout(() => currentGraphPanel?.refresh(), 500);
        }
      } catch (error) {
        // Silently fail if backend not running
      }
    })
  );

  // Watch for file save - refresh repo and graph
  context.subscriptions.push(
    vscode.workspace.onDidSaveTextDocument(async (doc) => {
      if (!isSupported(doc)) return;

      const repoPath = getRepoPath();
      if (!repoPath) return;

      try {
        console.log('File saved, refreshing repo...');
        await refreshRepo(repoPath, DEFAULT_PORT);

        if (currentGraphPanel) {
          setTimeout(() => {
            console.log('Refreshing graph after save...');
            currentGraphPanel?.refresh();
          }, 1500);
        }
      } catch (error) {
        // Silently fail if backend not running
      }
    })
  );

  // Watch for workspace folder changes - auto-scan new repos
  context.subscriptions.push(
    vscode.workspace.onDidChangeWorkspaceFolders(async (e) => {
      if (e.added.length > 0) {
        const newRepoPath = e.added[0].uri.fsPath;
        try {
          await refreshRepo(newRepoPath, DEFAULT_PORT);
          vscode.window.showInformationMessage(`Snipe: Scanned new repository`);
        } catch (error) {
          // Backend not running, silently fail
        }
      }
    })
  );

  const activeDoc = vscode.window.activeTextEditor?.document;
  if (activeDoc && isSupported(activeDoc)) {
    debouncedAnalysis(activeDoc);
  }
}

export function deactivate(): void {
  if (debounceTimer) clearTimeout(debounceTimer);
}

/**
 * Ensure every open supported document has an entry in allDiagnosticsMap,
 * then save the full combined diagnostics to the backend so the graph can
 * highlight errors across all files — not just the active one.
 */
async function analyzeAllOpenFiles(repoPath: string): Promise<void> {
  for (const document of vscode.workspace.textDocuments) {
    if (isSupported(document) && !allDiagnosticsMap.has(document.uri.fsPath)) {
      try {
        const res = await analyzeBuffer({
          content: document.getText(),
          file_path: document.uri.fsPath,
          repo_path: repoPath,
        });
        allDiagnosticsMap.set(document.uri.fsPath, res.diagnostics);
      } catch (error) {
        console.error(`Failed to analyze ${document.fileName}:`, error);
      }
    }
  }

  const allDiagnostics = Array.from(allDiagnosticsMap.values()).flat();

  try {
    await fetch(`http://127.0.0.1:${DEFAULT_PORT}/save_diagnostics`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ repo_path: repoPath, diagnostics: allDiagnostics }),
    });
  } catch (error) {
    console.error('Failed to save combined diagnostics:', error);
  }
}

function isSupported(doc: vscode.TextDocument): boolean {
  const ext = doc.fileName.split(".").pop()?.toLowerCase();
  return ext === "py" || ext === "c" || ext === "h";
}

function getRepoPath(): string | undefined {
  const folders = vscode.workspace.workspaceFolders;
  if (!folders?.length) return undefined;
  return folders[0].uri.fsPath;
}
