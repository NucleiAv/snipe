## Software Development Plan (SDP)

### 1. Project Overview
**Project Name:** Snipe

**Goal:**
Develop a real-time code analysis system that detects cross-file semantic errors, type inconsistencies, array bound violations, and symbol drift while the developer is typing—even before files are saved—without relying on external security scanning APIs or proprietary tools.

**Primary Use Case:**
- Hackathon demonstration and research prototype
- Developer productivity and security enhancement
- Real-time semantic feedback across an entire repository

---

### 2. System Architecture Overview

**High-Level Components:**
1. IDE Plugin (Client Layer)
2. Local Analysis Engine (Backend)
3. Repository Knowledge Graph (Data Layer)
4. AI Explanation Layer (Optional, replaceable with deterministic rules)
5. Visualization & Diagnostics UI

**Deployment Model:**
- Local developer machine only
- No external SaaS dependency required

---

### 3. Development Phases

#### Phase 1 – Core Infrastructure
- Build VSCode extension to capture unsaved buffer changes
- Implement file watcher for repository scanning
- Create AST parser using Tree-sitter

#### Phase 2 – Repository Knowledge Graph
- Extract symbols (variables, functions, structs, classes)
- Store symbol metadata (type, scope, file, line)
- Build dependency and reference graph

#### Phase 3 – Real-Time Semantic Analysis Engine
- Compare unsaved buffer symbols against repo knowledge graph
- Detect cross-file mismatches and violations
- Generate structured diagnostics

#### Phase 4 – Explanation & UX
- Convert diagnostics to human-readable messages
- Inline editor warnings
- Optional dependency graph visualization panel

#### Phase 5 – Testing & Demo
- Create synthetic vulnerable repositories
- Demonstrate live detection scenarios
- Performance profiling and optimization

---

### 4. Technology Stack
| Component | Technology | Justification |
|-----------|------------|---------------|
| IDE Plugin | TypeScript, VSCode API | Native editor integration |
| Parsing | Tree-sitter | Multi-language incremental parsing |
| Backend | Python (FastAPI) or Node.js | Lightweight local server |
| Graph Storage | JSON + NetworkX | Minimal dependency, fast iteration |
| UI Graph | D3.js or Mermaid | Lightweight visualization |
| AI (Optional) | Local LLM or deterministic rules | Avoid external APIs |

---

### 5. Milestones and Deliverables
| Milestone | Deliverable |
|-----------|-------------|
| M1 | Working VSCode plugin capturing unsaved code |
| M2 | Repo-wide symbol extraction |
| M3 | Live cross-file semantic detection |
| M4 | Inline diagnostics UI |
| M5 | Demo repository + video |

---

### 6. Risk Management
**Technical Risks:**
- Performance overhead from real-time parsing
- Partial AST due to incomplete code
- Language diversity complexity

**Mitigation:**
- Incremental parsing
- Graceful fallback to heuristic parsing
- Limit language scope in MVP (e.g., C/C++/Python/TypeScript)

---

### 7. Quality Assurance
- Unit tests for parser and analyzer
- Integration tests with VSCode extension
- Performance benchmarks (latency < 100ms per edit)

---

---
# Software Requirements Specification (SRS)

## 1. Introduction

### 1.1 Purpose
This document specifies the functional and non-functional requirements for Snipe, a real-time semantic code analysis system.

### 1.2 Scope
The system will analyze unsaved code edits in real time, compare them against repository-wide semantic metadata, and report cross-file inconsistencies and potential logic errors.

### 1.3 Definitions
- **Symbol:** Variable, function, struct, class, or constant
- **Repo Knowledge Graph (RKG):** Structured representation of symbols and relationships
- **Unsaved Buffer:** Code in editor not yet written to disk

---

## 2. Overall Description

### 2.1 Product Perspective
Snipe functions as a local developer tool integrated into VSCode. It runs an internal analysis server that maintains a repository semantic model.

### 2.2 User Classes
- Software developers
- Security researchers
- Hackathon judges (demo mode)

### 2.3 Operating Environment
- Windows, macOS, Linux
- VSCode IDE
- Local Python/Node runtime

---

## 3. Functional Requirements

### FR-1: Repository Symbol Extraction
**Description:**
The system shall parse all repository files and extract symbols and metadata.

**Inputs:** Source code files
**Outputs:** Symbol table with type, scope, location

---

### FR-2: Real-Time Unsaved Code Capture
**Description:**
The system shall capture code edits before file save using the IDE API.

---

### FR-3: Cross-File Type Consistency Detection
**Description:**
The system shall detect when a symbol is used with a different type than declared in another file.

**Example:** float vs int mismatch

---

### FR-4: Static Array Bounds Verification
**Description:**
The system shall detect index usage beyond statically declared array bounds.

---

### FR-5: Function Signature Drift Detection
**Description:**
The system shall detect when a function call does not match its latest signature in the repository.

---

### FR-6: Undefined and Shadowed Symbol Detection
**Description:**
The system shall detect references to undefined symbols and shadowed variables across scopes.

---

### FR-7: Semantic Diagnostics Generation
**Description:**
The system shall generate structured diagnostic messages with file and line references.

---

### FR-8: Inline Editor Warning Display
**Description:**
The system shall display warnings directly in the IDE editor.

---

### FR-9: Repository Knowledge Graph Visualization
**Description:**
The system shall visualize symbol relationships and dependencies.

---

## 4. Non-Functional Requirements

### NFR-1: Performance
- Real-time analysis latency < 100ms per keystroke batch

### NFR-2: Scalability
- Handle repositories up to 100k LOC in MVP

### NFR-3: Portability
- Cross-platform support
n### NFR-4: Security
- No external data transmission by default

### NFR-5: Extensibility
- Plugin-based rule system for additional languages and checks

---

## 5. System Interfaces

### 5.1 IDE Interface
- VSCode Extension API

### 5.2 Backend Interface
- Local HTTP or IPC API between extension and analyzer

### 5.3 Data Interface
- JSON-based symbol graph storage

---

## 6. Data Model

### Symbol Entity
- name
- type
- file_path
- line_number
- scope
- references[]

### Relationship Types
- CALLS
- DEFINES
- REFERENCES
- INHERITS

---

## 7. Algorithms & Processing

### 7.1 Symbol Extraction Algorithm
- Parse AST via Tree-sitter
- Traverse nodes to extract declarations

### 7.2 Live Diff Semantic Comparison
- Compare unsaved AST symbols against RKG
- Trigger rule-based checks

### 7.3 Rule Engine
- Deterministic rule definitions (YAML/JSON)
- Pluggable modules for future security checks

---

## 8. Constraints
- Limited language support in MVP
- No full symbolic execution in initial version
- No external SaaS dependency required

---

## 9. Future Enhancements
- Taint analysis for SQLi/XSS
- Memory lifetime analysis (UAF detection)
- AI-based logic bug prediction
- Multi-IDE support (JetBrains, Neovim)

---

## 10. Acceptance Criteria
- Detect cross-file type mismatch in real time
- Detect array out-of-bounds before save
- Show inline warning in editor
- Visualize repo symbol graph
- Demo with sample vulnerable repository

---

# Appendix A – Minimal Dependency Philosophy
- Prefer Tree-sitter for parsing
- Avoid proprietary security APIs
- Use deterministic static analysis rules
- Optional AI layer must be modular and removable



---
# MVP-Focused Component-Level Task Breakdown (Hackathon Scope)

## MVP Objective
Deliver a working prototype that demonstrates **real-time, cross-file semantic analysis on unsaved code** with clear visual diagnostics. The MVP will prioritize **novel USP features** over completeness.

### USP Features for Hackathon Demo
1. Real-time cross-file type mismatch detection (before save)
2. Static array out-of-bounds detection using repo context
3. Function signature drift detection
4. Inline IDE warnings with human-readable explanation
5. Minimal repo symbol graph visualization panel

---

## Component-Level Tasks

### Component A – VSCode Extension (Client)
**Goal:** Capture unsaved code and display diagnostics.

**Tasks:**
- A1: Initialize VSCode extension project (TypeScript)
- A2: Implement `onDidChangeTextDocument` listener
- A3: Serialize unsaved buffer and send to backend via HTTP/IPC
- A4: Receive diagnostics JSON and render inline warnings (VSCode Diagnostics API)
- A5: Add command to open Repo Knowledge Graph panel

**Deliverable:** Working VSCode plugin showing warnings while typing.

---

### Component B – Repository Parser & Symbol Extractor
**Goal:** Build a repository-wide symbol table.

**Tasks:**
- B1: Recursively scan repository files
- B2: Parse files using Tree-sitter
- B3: Extract symbols (variables, functions, arrays, types)
- B4: Store metadata (name, type, file, line, scope)
- B5: Persist symbol table as JSON

**Deliverable:** `repo_symbols.json`

---

### Component C – Live Semantic Analyzer
**Goal:** Compare unsaved buffer against repo knowledge graph.

**Tasks:**
- C1: Parse unsaved buffer via Tree-sitter
- C2: Extract symbols and references from buffer
- C3: Cross-file type consistency checker
- C4: Static array bounds checker
- C5: Function signature mismatch checker

**Deliverable:** Structured diagnostics JSON.

---

### Component D – Explanation Engine
**Goal:** Convert diagnostics to human-readable messages.

**Tasks:**
- D1: Rule-based explanation templates (no external AI required)
- D2: Optional local LLM module (pluggable)

**Deliverable:** One-line explanations for each diagnostic.

---

### Component E – Repo Knowledge Graph Visualization (Optional but WOW Factor)
**Goal:** Show symbol relationships visually.

**Tasks:**
- E1: Build dependency graph (NetworkX or JSON graph)
- E2: Render graph using D3.js or Mermaid in VSCode WebView

**Deliverable:** Interactive dependency graph panel.

---

# Directory / Repository Structure Specification

```
Snipe/
│
├── extension/                 # VSCode plugin
│   ├── src/
│   │   ├── extension.ts       # Entry point
│   │   ├── diagnostics.ts      # Inline warnings logic
│   │   ├── apiClient.ts        # Backend IPC client
│   │   └── webview.ts           # Graph visualization panel
│   └── package.json
│
├── backend/
│   ├── server.py or server.js  # Local analysis server
│   ├── parser/
│   │   ├── repo_parser.py       # Repo scanner
│   │   ├── buffer_parser.py     # Unsaved buffer parser
│   │   └── symbol_extractor.py  # AST symbol extraction
│   ├── analyzer/
│   │   ├── type_checker.py
│   │   ├── bounds_checker.py
│   │   └── signature_checker.py
│   ├── rules/
│   │   └── rules.json            # Deterministic rule definitions
│   ├── graph/
│   │   └── repo_graph.py          # Knowledge graph builder
│   └── data/
│       └── repo_symbols.json
│
├── demo_repo/                  # Vulnerable sample repo for demo
├── tests/
│   └── unit_tests.py
└── README.md
```

---

# Pseudo-Code Section (AI-Agent Friendly)

## 1. Repository Symbol Extraction

```
function buildRepoSymbolTable(repo_path):
    symbols = []
    for file in repo_path.recursive_files():
        ast = tree_sitter.parse(file)
        for node in ast.declaration_nodes():
            symbol = {
                name: node.name,
                type: node.type,
                file: file.path,
                line: node.line,
                scope: node.scope
            }
            symbols.append(symbol)
    save_json(symbols, repo_symbols.json)
```

---

## 2. Unsaved Buffer Analysis Pipeline

```
function analyzeUnsavedBuffer(buffer_code, repo_symbols):
    buffer_ast = tree_sitter.parse(buffer_code)
    buffer_refs = extract_references(buffer_ast)
    diagnostics = []

    diagnostics += checkTypeMismatch(buffer_refs, repo_symbols)
    diagnostics += checkArrayBounds(buffer_refs, repo_symbols)
    diagnostics += checkFunctionSignatures(buffer_refs, repo_symbols)

    return diagnostics
```

---

## 3. Cross-File Type Mismatch Detection

```
function checkTypeMismatch(buffer_refs, repo_symbols):
    for ref in buffer_refs:
        repo_def = repo_symbols.find(name=ref.name)
        if repo_def and repo_def.type != ref.type:
            emitDiagnostic(
                message = f"{ref.name} declared as {repo_def.type} in {repo_def.file}:{repo_def.line} but used as {ref.type}",
                severity = WARNING
            )
```

---

## 4. Static Array Bounds Detection

```
function checkArrayBounds(buffer_refs, repo_symbols):
    for ref in buffer_refs where ref.is_array_access:
        repo_def = repo_symbols.find(name=ref.array_name)
        if repo_def and ref.index >= repo_def.array_size:
            emitDiagnostic(
                message = f"Index {ref.index} exceeds declared size {repo_def.array_size} in {repo_def.file}:{repo_def.line}",
                severity = ERROR
            )
```

---

## 5. Function Signature Drift Detection

```
function checkFunctionSignatures(buffer_refs, repo_symbols):
    for call in buffer_refs where call.is_function_call:
        repo_def = repo_symbols.find_function(call.name)
        if repo_def and len(call.args) != len(repo_def.params):
            emitDiagnostic(
                message = f"Function {call.name} expects {len(repo_def.params)} args but {len(call.args)} provided",
                severity = WARNING
            )
```

---

## 6. Diagnostics Output Format

```
{
  "file": "current_file.c",
  "line": 42,
  "severity": "ERROR",
  "message": "Index 12 exceeds declared size 10 in core.c:34"
}
```

---

# MVP Build Steps (Hackathon Timeline)

## Day 0 – Setup (2h)
- Initialize repo structure
- Bootstrap VSCode extension
- Setup backend server

## Day 1 – Core USP Features (12–18h)
- Repo symbol extraction
- Unsaved buffer capture
- Type mismatch checker
- Array bounds checker
- Inline diagnostics display

## Day 2 – Demo Polish (8–12h)
- Function signature checker
- Repo graph visualization
- Demo vulnerable repo
- Performance optimization
- Pitch & demo script

---

# Hackathon Demo Scenario

1. Show repo with `int arr[10]` in core.c
2. Type `arr[12]` in unsaved file
3. Warning appears instantly (before save)
4. Show `float balance` in Python file and `int balance` in Go file → instant mismatch warning
5. Visualize repo symbol graph

**Key USP Line:**
> “We catch cross-file bugs before you even save your file.”

---

# Acceptance Criteria (MVP)
- Unsaved code triggers backend analysis
- Cross-file type mismatch detected live
- Array out-of-bounds detected live
- Inline VSCode warnings displayed
- Demo repository shows at least 3 live bug detections

