/**
 * HTTP client to Snipe backend (local analysis server).
 */

const DEFAULT_PORT = 8765;
const DEFAULT_HOST = "127.0.0.1";

export interface AnalyzeRequest {
  content: string;
  file_path: string;
  repo_path: string;
  language?: string;
}

export interface DiagnosticItem {
  file: string;
  line: number;
  severity: string;
  message: string;
  code?: string;
}

export interface AnalyzeResponse {
  diagnostics: DiagnosticItem[];
  file: string;
}

export interface GraphResponse {
  nodes: Array<{ id: string; label: string; kind: string; type?: string; file_path: string; line: number }>;
  edges: Array<{ source: string; target: string; type: string }>;
}

function baseUrl(port?: number): string {
  const p = port ?? DEFAULT_PORT;
  return `http://${DEFAULT_HOST}:${p}`;
}

export async function analyzeBuffer(
  request: AnalyzeRequest,
  port: number = DEFAULT_PORT
): Promise<AnalyzeResponse> {
  const res = await fetch(`${baseUrl(port)}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Snipe analyze failed: ${res.status} ${text}`);
  }
  return res.json() as Promise<AnalyzeResponse>;
}

export async function refreshRepo(repoPath: string, port: number = DEFAULT_PORT): Promise<{ symbol_count: number }> {
  const res = await fetch(`${baseUrl(port)}/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ repo_path: repoPath }),
  });
  if (!res.ok) throw new Error(`Snipe refresh failed: ${res.status}`);
  return res.json() as Promise<{ symbol_count: number }>;
}

export async function getGraph(repoPath: string, port: number = DEFAULT_PORT): Promise<GraphResponse> {
  const url = `${baseUrl(port)}/graph?repo_path=${encodeURIComponent(repoPath)}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Snipe graph failed: ${res.status}`);
  return res.json() as Promise<GraphResponse>;
}

export async function healthCheck(port: number = DEFAULT_PORT): Promise<boolean> {
  try {
    const res = await fetch(`${baseUrl(port)}/health`);
    return res.ok;
  } catch {
    return false;
  }
}
