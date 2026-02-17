# Snipe
![snipe logo](https://github.com/NucleiAv/snipe/blob/main/snipe-logo.png)

Real-time code analysis that detects **cross-file semantic errors**, type inconsistencies, array bound violations, and function signature drift **while you type**—before files are saved—without external security APIs.

**USP:** *"We catch cross-file bugs before you even save your file."*

---
Software Milestone and SRS - [snipe software docs](https://github.com/NucleiAv/snipe/blob/main/live_repo_aware_semantic_guardian_sdp_and_srs.md)

Contributors must read - [snipe contributions doc](https://github.com/NucleiAv/snipe/blob/main/CONTRIBUTING.md)

Comparison of snipe with other exisitng tools - [snipe vs others](https://github.com/NucleiAv/snipe/blob/main/snipe_VS_other.md)

Supported handled error - [supported error handling](https://github.com/NucleiAv/snipe/blob/extend-error-handling/supported_error_handling.md)

---

## Features

- **Real-time cross-file type mismatch** detection (unsaved buffer vs repo)
- **Static array out-of-bounds** detection using repo context
- **Function signature drift** detection (argument count)
- **Inline VSCode warnings** with human-readable messages
- **Repo Knowledge Graph** visualization panel (symbols and REFERENCES)

## Architecture

| Component        | Role |
|-----------------|------|
| **VSCode extension** | Captures unsaved buffer, sends to Snipe backend, shows diagnostics and graph panel |
| **Backend (Python/FastAPI)** | Repo parser (Tree-sitter), symbol table, type/bounds/signature analyzers |
| **Repo symbols** | Stored in `backend/data/repo_symbols.json` (built on first analyze or Refresh) |

## Quick Start

Do these in order: **1. Backend** → **2. Extension** → **3. Open hub & Command Palette**.

---

### 1. Start the backend (do this first)

Open a terminal in the project folder, then:

**Windows (PowerShell or CMD):**
```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn server:app --reload --port 8765
```

**macOS / Linux:**
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn server:app --reload --port 8765
```

Leave this terminal open. The Snipe backend will be at `http://127.0.0.1:8765`.

---

### 2. Build and run the extension

Requires **Node.js** and **npm**. In a **new** terminal (project folder):

**Windows:**
```powershell
cd extension
npm install
npm run compile
```

**macOS / Linux:**
```bash
cd extension
npm install
npm run compile
```

Then in **VS Code**:
- Open the **Snipe project folder** (the repo root, e.g. `ai-code-scanner`).
- **Run > Start Debugging** (or press **F5**).  
  A second window opens: **[Extension Development Host]** — that’s where Snipe is loaded.

*If you don’t have Node/npm:* see the **Node.js / npm** section below.

---

### 3. Open the hub and use the Command Palette

In the **[Extension Development Host]** window:

1. **Open a folder**  
   **File → Open Folder…** and choose your repo (e.g. `demo_repo` or the folder that contains it). That folder is the “hub” Snipe will analyze.

2. **Open the Command Palette**  
   - **Windows / Linux:** `Ctrl+Shift+P`  
   - **macOS:** `Cmd+Shift+P`  

3. Run Snipe commands:
   - Type `Snipe` or `Refresh` → choose **Snipe: Refresh Repository Symbols** (build the symbol table).
   - Type `Snipe` or `Graph` → choose **Snipe: Open Repo Knowledge Graph** (open the graph panel).

4. Edit a file (e.g. `main.c`). You should see live diagnostics (e.g. array out-of-bounds) and the **Problems** panel (**View → Problems** or **Ctrl+Shift+M** / **Cmd+Shift+M**).

---

### Reloading after code changes

| What changed | What to do |
|--------------|------------|
| **Backend** (e.g. `server.py`, `parser/`, `analyzer/`) | With `uvicorn server:app --reload`, the backend restarts automatically. If it doesn’t, stop it (**Ctrl+C**) and run the same `uvicorn` command again in the backend terminal. |
| **Extension** (e.g. `extension/src/*.ts`) | 1. Run `npm run compile` in the `extension` folder. 2. In the **[Extension Development Host]** window, open Command Palette (**Ctrl+Shift+P** / **Cmd+Shift+P**) → run **Developer: Reload Window**. The extension reloads with your changes. |
| **Both** | Restart uvicorn if needed; recompile extension and **Developer: Reload Window** in the Extension Development Host. |

**Summary:** Backend = leave uvicorn running (it auto-reloads). Extension = `npm run compile` then **Developer: Reload Window** in the dev host.

---

### Node.js / npm (if not installed)

**Option A – Node binary (works on Windows, macOS, Linux; no apt/nvm):**

Download and unpack [Node.js LTS](https://nodejs.org/), or on **Linux** (e.g. Kali):

```bash
cd ~
curl -sL https://nodejs.org/dist/v20.18.0/node-v20.18.0-linux-x64.tar.xz -o node.tar.xz
tar -xf node.tar.xz
export PATH="$HOME/node-v20.18.0-linux-x64/bin:$PATH"
echo 'export PATH="$HOME/node-v20.18.0-linux-x64/bin:$PATH"' >> ~/.zshrc
```

**Option B – nvm (bash only).** On **macOS/Linux** with zsh, run the nvm script inside `bash`, then use `nvm install --lts` and `nvm use --lts` before building the extension.

## Demo repository

`demo_repo/` contains intentional issues:

- **main.c** – `arr[12]` (array size 10 in `core.c`) → array bounds error.
- **app.py** – `greet("X", "Hi", "extra")` and `compute(1, 2)` → signature drift.
- **utils.py** / **core.c** – `balance` as int vs float for cross-file type demo.

## Output

The terminal ouput after running the whole extension will be something like this (below)
```
┌──(my-py-venv)─(kali㉿kali)-[snipe/backend]
└─$ cd /backend
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
source .venv/bin/activate
uvicorn server:app --reload --port 8765
INFO:     Will watch for changes in these directories: ['snipe/backend']
INFO:     Uvicorn running on http://127.0.0.1:8765 (Press CTRL+C to quit)
INFO:     Started reloader process [28311] using WatchFiles
INFO:     Started server process [28314]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:parser.repo_parser:Scanned 4 supported files, got 14 symbols
INFO:parser.symbol_extractor:C regex fallback added 3 array_access ref(s)
INFO:server:Analyze /media/sf_ai-code-scanner/demo_repo/main.c: 7 buffer_refs, 4 diagnostics
INFO:     127.0.0.1:57936 - "POST /analyze HTTP/1.1" 200 OK
INFO:parser.symbol_extractor:C regex fallback added 3 array_access ref(s)
INFO:server:Analyze /media/sf_ai-code-scanner/demo_repo/main.c: 7 buffer_refs, 4 diagnostics
INFO:     127.0.0.1:57936 - "POST /analyze HTTP/1.1" 200 OK
INFO:parser.symbol_extractor:C regex fallback added 3 array_access ref(s)
INFO:server:Analyze /media/sf_ai-code-scanner/demo_repo/main.c: 7 buffer_refs, 2 diagnostics
INFO:     127.0.0.1:42362 - "POST /analyze HTTP/1.1" 200 OK
INFO:parser.symbol_extractor:C regex fallback added 3 array_access ref(s)
INFO:server:Analyze /media/sf_ai-code-scanner/demo_repo/main.c: 7 buffer_refs, 4 diagnostics
INFO:     127.0.0.1:42362 - "POST /analyze HTTP/1.1" 200 OK
INFO:parser.symbol_extractor:C regex fallback added 3 array_access ref(s)
INFO:server:Analyze /media/sf_ai-code-scanner/demo_repo/main.c: 7 buffer_refs, 2 diagnostics
INFO:     127.0.0.1:42362 - "POST /analyze HTTP/1.1" 200 OK
INFO:parser.symbol_extractor:C regex fallback added 2 array_access ref(s)
INFO:server:Analyze /media/sf_ai-code-scanner/demo_repo/core.c: 3 buffer_refs, 2 diagnostics
INFO:     127.0.0.1:58628 - "POST /analyze HTTP/1.1" 200 OK
INFO:parser.symbol_extractor:C regex fallback added 3 array_access ref(s)
INFO:server:Analyze /media/sf_ai-code-scanner/demo_repo/main.c: 7 buffer_refs, 2 diagnostics
INFO:     127.0.0.1:37754 - "POST /analyze HTTP/1.1" 200 OK
INFO:parser.symbol_extractor:C regex fallback added 3 array_access ref(s)
INFO:server:Analyze /media/sf_ai-code-scanner/demo_repo/main.c: 7 buffer_refs, 4 diagnostics
```

## Directory layout

```
Snipe/
├── extension/          # VSCode plugin
│   ├── src/
│   │   ├── extension.ts
│   │   ├── diagnostics.ts
│   │   ├── apiClient.ts
│   │   └── webview.ts
│   └── package.json
├── backend/
│   ├── server.py
│   ├── parser/         # repo_parser, buffer_parser, symbol_extractor
│   ├── analyzer/       # type_checker, bounds_checker, signature_checker
│   ├── graph/          # repo_graph
│   ├── rules/rules.json
│   └── data/repo_symbols.json
├── demo_repo/
├── tests/unit_tests.py
├── CONTRIBUTING.md
├── License
└── README.md
```

## API (backend)

- `POST /analyze` – body: `{ "content", "file_path", "repo_path" }` → `{ "diagnostics": [...] }`
- `POST /refresh` – body: `{ "repo_path" }` → rescans repo, rebuilds symbol table
- `GET /symbols?repo_path=...` – return symbol table
- `GET /graph?repo_path=...` – return nodes + edges for visualization
- `GET /health` – health check

## Acceptance criteria (MVP)

- [x] Unsaved code triggers backend analysis
- [x] Cross-file type mismatch detected live
- [x] Array out-of-bounds detected live
- [x] Inline VSCode warnings
- [x] Demo repo with at least 3 live bug detections

## Run tests

From project root:

```bash
python tests/unit_tests.py
```

## Notes
The default branch has been renamed!
`master` is now named `main`

If you have a local clone already where branch name is still `master`, you can update it by running the following commands.

```
git branch -m master main
git fetch origin
git branch -u origin/main main
git remote set-head origin -a
```
