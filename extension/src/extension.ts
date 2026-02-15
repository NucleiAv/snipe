/**
 * Snipe VSCode Extension – Entry point.
 * Captures unsaved buffer, sends to backend, displays inline diagnostics.
 */

import * as vscode from "vscode";
import { analyzeBuffer, getGraph, refreshRepo, healthCheck } from "./apiClient";
import { setDiagnostics, clearDiagnostics } from "./diagnostics";
import { openGraphPanel, refreshGraph } from "./webview";

const DIAGNOSTIC_COLLECTION = "snipe";
const DEFAULT_PORT = 8765;
const DEBOUNCE_MS = 300;

let diagnosticCollection: vscode.DiagnosticCollection;
let debounceTimer: NodeJS.Timeout | undefined;

export function activate(context: vscode.ExtensionContext): void {
  diagnosticCollection = vscode.languages.createDiagnosticCollection(DIAGNOSTIC_COLLECTION);
  context.subscriptions.push(diagnosticCollection);

  const runAnalysis = (doc: vscode.TextDocument) => {
    if (!isSupported(doc)) return;
    const repoPath = getRepoPath();
    if (!repoPath) return;
    clearDiagnostics(doc.uri, diagnosticCollection);
    analyzeBuffer({
      content: doc.getText(),
      file_path: doc.uri.fsPath,
      repo_path: repoPath,
    })
      .then((res) => {
        setDiagnostics(doc.uri, res.diagnostics, diagnosticCollection);
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
      if (e.document === vscode.window.activeTextEditor?.document) {
        debouncedAnalysis(e.document);
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
    vscode.window.onDidChangeActiveTextEditor((editor) => {
      if (editor && isSupported(editor.document)) {
        debouncedAnalysis(editor.document);
      }
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("snipe.openGraph", () => {
      const repoPath = getRepoPath();
      if (!repoPath) {
        vscode.window.showWarningMessage("Snipe: Open a workspace folder (repo root) first.");
        return;
      }
      openGraphPanel(context, () => getGraph(repoPath, DEFAULT_PORT));
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
        refreshGraph(() => getGraph(repoPath, DEFAULT_PORT));
        const doc = vscode.window.activeTextEditor?.document;
        if (doc && isSupported(doc)) runAnalysis(doc);
      } catch (e) {
        vscode.window.showErrorMessage("Snipe: Refresh failed. " + (e instanceof Error ? e.message : String(e)));
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

function isSupported(doc: vscode.TextDocument): boolean {
  const ext = doc.fileName.split(".").pop()?.toLowerCase();
  return ext === "py" || ext === "c" || ext === "h";
}

function getRepoPath(): string | undefined {
  const folders = vscode.workspace.workspaceFolders;
  if (!folders?.length) return undefined;
  return folders[0].uri.fsPath;
}
