/**
 * Map Snipe diagnostics to VSCode Diagnostics API and set them on the editor.
 */

import * as vscode from "vscode";
import type { DiagnosticItem } from "./apiClient";

const SNIPE_SOURCE = "Snipe";

function toVsSeverity(severity: string): vscode.DiagnosticSeverity {
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

export function setDiagnostics(
  uri: vscode.Uri,
  items: DiagnosticItem[],
  collection: vscode.DiagnosticCollection
): void {
  // We requested analysis for this document; show all returned diagnostics (path may differ by normalization).
  const diagnostics: vscode.Diagnostic[] = items.map((d) => {
    const line = Math.max(0, d.line - 1);
    const range = new vscode.Range(line, 0, line, 1000);
    const diag = new vscode.Diagnostic(range, d.message, toVsSeverity(d.severity));
    diag.source = SNIPE_SOURCE;
    if (d.code) diag.code = d.code;
    return diag;
  });
  if (diagnostics.length > 0) {
    collection.set(uri, diagnostics);
  } else {
    collection.delete(uri);
  }
}

export function clearDiagnostics(uri: vscode.Uri, collection: vscode.DiagnosticCollection): void {
  collection.delete(uri);
}
