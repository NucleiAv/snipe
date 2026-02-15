"use strict";
/**
 * Map Snipe diagnostics to VSCode Diagnostics API and set them on the editor.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.setDiagnostics = setDiagnostics;
exports.clearDiagnostics = clearDiagnostics;
const vscode = require("vscode");
const SNIPE_SOURCE = "Snipe";
function toVsSeverity(severity) {
    switch (severity.toUpperCase()) {
        case "ERROR":
            return vscode.DiagnosticSeverity.Error;
        case "WARNING":
            return vscode.DiagnosticSeverity.Warning;
        case "INFO":
            return vscode.DiagnosticSeverity.Information;
        default:
            return vscode.DiagnosticSeverity.Warning;
    }
}
function setDiagnostics(uri, items, collection) {
    // We requested analysis for this document; show all returned diagnostics (path may differ by normalization).
    const diagnostics = items.map((d) => {
        const line = Math.max(0, d.line - 1);
        const range = new vscode.Range(line, 0, line, 1000);
        const diag = new vscode.Diagnostic(range, d.message, toVsSeverity(d.severity));
        diag.source = SNIPE_SOURCE;
        if (d.code)
            diag.code = d.code;
        return diag;
    });
    if (diagnostics.length > 0) {
        collection.set(uri, diagnostics);
    }
    else {
        collection.delete(uri);
    }
}
function clearDiagnostics(uri, collection) {
    collection.delete(uri);
}
//# sourceMappingURL=diagnostics.js.map