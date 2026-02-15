"use strict";
/**
 * Snipe VSCode Extension – Entry point.
 * Captures unsaved buffer, sends to backend, displays inline diagnostics.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = require("vscode");
const apiClient_1 = require("./apiClient");
const diagnostics_1 = require("./diagnostics");
const webview_1 = require("./webview");
const DIAGNOSTIC_COLLECTION = "snipe";
const DEFAULT_PORT = 8765;
const DEBOUNCE_MS = 300;
let diagnosticCollection;
let debounceTimer;
function activate(context) {
    diagnosticCollection = vscode.languages.createDiagnosticCollection(DIAGNOSTIC_COLLECTION);
    context.subscriptions.push(diagnosticCollection);
    const runAnalysis = (doc) => {
        if (!isSupported(doc))
            return;
        const repoPath = getRepoPath();
        if (!repoPath)
            return;
        (0, diagnostics_1.clearDiagnostics)(doc.uri, diagnosticCollection);
        (0, apiClient_1.analyzeBuffer)({
            content: doc.getText(),
            file_path: doc.uri.fsPath,
            repo_path: repoPath,
        })
            .then((res) => {
            (0, diagnostics_1.setDiagnostics)(doc.uri, res.diagnostics, diagnosticCollection);
        })
            .catch(() => {
            // Backend not running or error – leave diagnostics clear or show status
        });
    };
    const debouncedAnalysis = (doc) => {
        if (debounceTimer)
            clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => runAnalysis(doc), DEBOUNCE_MS);
    };
    context.subscriptions.push(vscode.workspace.onDidChangeTextDocument((e) => {
        if (e.document === vscode.window.activeTextEditor?.document) {
            debouncedAnalysis(e.document);
        }
    }));
    context.subscriptions.push(vscode.workspace.onDidOpenTextDocument((doc) => {
        if (doc === vscode.window.activeTextEditor?.document && isSupported(doc)) {
            debouncedAnalysis(doc);
        }
    }));
    context.subscriptions.push(vscode.window.onDidChangeActiveTextEditor((editor) => {
        if (editor && isSupported(editor.document)) {
            debouncedAnalysis(editor.document);
        }
    }));
    context.subscriptions.push(vscode.commands.registerCommand("snipe.openGraph", () => {
        const repoPath = getRepoPath();
        if (!repoPath) {
            vscode.window.showWarningMessage("Snipe: Open a workspace folder (repo root) first.");
            return;
        }
        (0, webview_1.openGraphPanel)(context, () => (0, apiClient_1.getGraph)(repoPath, DEFAULT_PORT));
    }));
    context.subscriptions.push(vscode.commands.registerCommand("snipe.refreshRepo", async () => {
        const repoPath = getRepoPath();
        if (!repoPath) {
            vscode.window.showWarningMessage("Snipe: Open a workspace folder (repo root) first.");
            return;
        }
        const ok = await (0, apiClient_1.healthCheck)(DEFAULT_PORT);
        if (!ok) {
            vscode.window.showErrorMessage("Snipe: Backend not running. Start it with: cd backend && uvicorn server:app --reload --port 8765");
            return;
        }
        try {
            const res = await (0, apiClient_1.refreshRepo)(repoPath, DEFAULT_PORT);
            vscode.window.showInformationMessage(`Snipe: Refreshed ${res.symbol_count} symbols.`);
            (0, webview_1.refreshGraph)(() => (0, apiClient_1.getGraph)(repoPath, DEFAULT_PORT));
            const doc = vscode.window.activeTextEditor?.document;
            if (doc && isSupported(doc))
                runAnalysis(doc);
        }
        catch (e) {
            vscode.window.showErrorMessage("Snipe: Refresh failed. " + (e instanceof Error ? e.message : String(e)));
        }
    }));
    const activeDoc = vscode.window.activeTextEditor?.document;
    if (activeDoc && isSupported(activeDoc)) {
        debouncedAnalysis(activeDoc);
    }
}
function deactivate() {
    if (debounceTimer)
        clearTimeout(debounceTimer);
}
function isSupported(doc) {
    const ext = doc.fileName.split(".").pop()?.toLowerCase();
    return ext === "py" || ext === "c" || ext === "h";
}
function getRepoPath() {
    const folders = vscode.workspace.workspaceFolders;
    if (!folders?.length)
        return undefined;
    return folders[0].uri.fsPath;
}
//# sourceMappingURL=extension.js.map