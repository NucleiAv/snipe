/**
 * Map Snipe diagnostics to VSCode Diagnostics API and set them on the editor.
 */

import * as vscode from "vscode";
import type { DiagnosticItem } from "./apiClient";

const SNIPE_SOURCE = "Snipe";
const DEFAULT_PORT = 8765;
const DEFAULT_HOST = "127.0.0.1";

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

async function enhanceDiagnosticWithAI(
  diagnostic: DiagnosticItem,
  document: vscode.TextDocument
): Promise<string> {
  try {
    // Extract code context: 5 lines before and after the error
    const errorLine = Math.max(0, diagnostic.line - 1);
    const startLine = Math.max(0, errorLine - 5);
    const endLine = Math.min(document.lineCount - 1, errorLine + 5);

    let codeContext = "";
    for (let i = startLine; i <= endLine; i++) {
      const lineText = document.lineAt(i).text;
      const marker = i === errorLine ? " // <- ERROR HERE" : "";
      codeContext += `${i + 1}: ${lineText}${marker}\n`;
    }

    // Call backend /explain endpoint
    const url = `http://${DEFAULT_HOST}:${DEFAULT_PORT}/explain`;
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        diagnostic: {
          message: diagnostic.message,
          severity: diagnostic.severity,
          code: diagnostic.code || "",
          file: diagnostic.file,
          line: diagnostic.line,
        },
        code_context: codeContext,
      }),
    });

    if (!response.ok) {
      console.warn(`Failed to get AI explanation: ${response.status}`);
      return diagnostic.message;
    }

    const data = (await response.json()) as { explanation?: string; error?: string };

    if (data.explanation) {
      // Format: Original message + AI explanation
      return `${diagnostic.message}\n\n💡 AI Suggestion:\n${data.explanation}\n\n`;
    } else {
      // AI not available or failed, return original message
      return diagnostic.message;
    }
  } catch (error) {
    console.warn("Error enhancing diagnostic with AI:", error);
    return diagnostic.message;
  }
}

export async function setDiagnostics(
  uri: vscode.Uri,
  items: DiagnosticItem[],
  collection: vscode.DiagnosticCollection
): Promise<void> {
  // Open document to get code context
  const document = await vscode.workspace.openTextDocument(uri);

  // Enhance diagnostics with AI explanations
  const enhancedItems = await Promise.all(
    items.map(async (d) => {
      const enhancedMessage = await enhanceDiagnosticWithAI(d, document);
      return { ...d, message: enhancedMessage };
    })
  );

  // Map to VSCode diagnostics
  const diagnostics: vscode.Diagnostic[] = enhancedItems.map((d) => {
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
