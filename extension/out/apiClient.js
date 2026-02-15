"use strict";
/**
 * HTTP client to Snipe backend (local analysis server).
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.analyzeBuffer = analyzeBuffer;
exports.refreshRepo = refreshRepo;
exports.getGraph = getGraph;
exports.healthCheck = healthCheck;
const DEFAULT_PORT = 8765;
const DEFAULT_HOST = "127.0.0.1";
function baseUrl(port) {
    const p = port ?? DEFAULT_PORT;
    return `http://${DEFAULT_HOST}:${p}`;
}
async function analyzeBuffer(request, port = DEFAULT_PORT) {
    const res = await fetch(`${baseUrl(port)}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
    });
    if (!res.ok) {
        const text = await res.text();
        throw new Error(`Snipe analyze failed: ${res.status} ${text}`);
    }
    return res.json();
}
async function refreshRepo(repoPath, port = DEFAULT_PORT) {
    const res = await fetch(`${baseUrl(port)}/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_path: repoPath }),
    });
    if (!res.ok)
        throw new Error(`Snipe refresh failed: ${res.status}`);
    return res.json();
}
async function getGraph(repoPath, port = DEFAULT_PORT) {
    const url = `${baseUrl(port)}/graph?repo_path=${encodeURIComponent(repoPath)}`;
    const res = await fetch(url);
    if (!res.ok)
        throw new Error(`Snipe graph failed: ${res.status}`);
    return res.json();
}
async function healthCheck(port = DEFAULT_PORT) {
    try {
        const res = await fetch(`${baseUrl(port)}/health`);
        return res.ok;
    }
    catch {
        return false;
    }
}
//# sourceMappingURL=apiClient.js.map