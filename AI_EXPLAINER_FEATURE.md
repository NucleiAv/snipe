# Snipe AI Explainer Feature

When Snipe detects a diagnostic error or warning in your code, the AI Explainer
generates a plain-English explanation of what the problem is, why it matters,
and how to fix it — powered by Anthropic Claude (with Google Gemini as a secondary option).

---

## Overview

Without AI explanations, a Snipe diagnostic looks like:

> `TYPE_MISMATCH: Variable 'count' assigned float but declared as int`

With the AI Explainer, the sidebar shows:

> *"You're storing a floating-point result (e.g. 3.14) into a variable that was
> declared as an integer. Python will silently truncate the decimal part, which
> can cause incorrect totals. Fix: either declare `count` as `float`, or use
> `int(result)` to make the truncation explicit."*

---

## Which AI APIs Are Used and Why

### Primary: Anthropic Claude (`claude-3-5-sonnet-20241022`)

Claude Sonnet is used as the primary provider because:

- **Free tier** — generous quota suitable for local development (see Cost section).
- **Speed** — Flash is optimised for low latency, so explanations appear quickly.
- **Quality** — Produces accurate, actionable explanations for the targeted
  diagnostic types Snipe raises (type mismatches, array bounds, signature errors).

### Fallback: Gemini (`gemini-2.5-flash`)

Gemini is available as a fallback if `GEMINI_API_KEY` is set.  The `AIExplainer` class tries Claude first if both keys are present, otherwise whichever key is available is used.

---

## New Files Created

| File | Purpose |
|------|---------|
| `backend/explainer/__init__.py` | Exposes `get_explainer()` singleton helper |
| `backend/explainer/ai_explainer.py` | `AIExplainer` class — prompt construction, API calls, provider selection |

---

## How It Works — Step by Step

### 1. Error Detection (existing analysers)

```
User edits buffer
  │
  └─ extension.ts: runAnalysis(doc)
       │
       └─ POST /analyze  { content, file_path, repo_path }
            │
            ├─ check_type_mismatch()      → TypeMismatch diagnostics
            ├─ check_array_bounds()       → OutOfBounds diagnostics
            └─ check_function_signatures() → SignatureMismatch diagnostics
```

Each checker returns a list of `Diagnostic` objects with:
`{ file, line, severity, message, code }`.

### 2. Code Context Extraction

The VS Code extension (or API caller) is responsible for supplying the
`code_context` string — typically a few lines around the error line extracted
from the buffer.  This gives the AI model enough information to make the
explanation specific to the user's actual code rather than generic.

### 3. API Call (backend/explainer/ai_explainer.py)

```python
AIExplainer.explain_diagnostic(diagnostic, code_context)
  │
  ├─ Builds prompt:
  │     "You are a helpful programming assistant …
  │      Error: {message}   Severity: {severity}
  │      File: {file}       Line: {line}
  │      Code context: ```{code_context}```
  │      Explain in ≤150 words: what it means, why it's a problem, how to fix it."
  │
  └─ Calls provider:
       Gemini: client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
       Claude: client.messages.create(model="claude-3-5-sonnet-20241022", …)
```

The response is trimmed and returned as a plain string.  If the API call fails
(network error, quota exceeded, invalid key), the function returns `None` and
the UI falls back to showing only the raw diagnostic message.

### 4. Explanation Displayed

```
POST /explain  { diagnostic: {...}, code_context: "…" }
  │
  └─ ai_explainer.explain_diagnostic(…)
       → returns explanation string (or None)
  │
  └─ response: { "explanation": "…" }
       │
       └─ VS Code sidebar renders the explanation below the diagnostic
```

---

## API Endpoints Added

### POST /explain

Generate an AI explanation for a single diagnostic.

**Body:**
```json
{
  "diagnostic": {
    "file": "app.py",
    "line": 42,
    "severity": "error",
    "message": "TYPE_MISMATCH: …",
    "code": "E001"
  },
  "code_context": "result = calculate(x)\ncount = result  # line 42\nprint(count)"
}
```

**Response (success):**
```json
{ "explanation": "You're assigning a float to an int variable …" }
```

**Response (AI unavailable):**
```json
{ "explanation": null, "error": "AI explanations not available. Check GOOGLE_API_KEY." }
```

### POST /save_diagnostics

*(Shared with the graph feature — see GRAPH_FEATURE.md)*

Saves combined diagnostics from all open files to `.snipe/diagnostics.json`.
Used by the graph to highlight error nodes, and could be used by future
features that need a persistent snapshot of current diagnostics.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_API_KEY` | Yes (for Gemini) | Google AI Studio API key. Get one at https://aistudio.google.com/app/apikey |
| `ANTHROPIC_API_KEY` | No (optional Claude fallback) | Anthropic Console API key |

Store these in `backend/.env`:

```env
GOOGLE_API_KEY=AIza...
ANTHROPIC_API_KEY=sk-ant-...
```

`python-dotenv` loads this file automatically when the backend starts.
**Never commit `.env` to git** — it is listed in `.gitignore`.

---

## How to Test

### Quick test via curl

```bash
# Start backend
cd backend && uvicorn server:app --reload --port 8765

# Trigger an explanation
curl -X POST http://localhost:8765/explain \
  -H "Content-Type: application/json" \
  -d '{
    "diagnostic": {
      "file": "app.py", "line": 10, "severity": "error",
      "message": "TYPE_MISMATCH: Variable x assigned float, declared int",
      "code": "E001"
    },
    "code_context": "x: int = 0\nx = 3.14"
  }'
```

### Test via the extension

1. Open a `.py` or `.c` file with a known type error.
2. Wait for Snipe diagnostics to appear (squiggles in editor).
3. Click the diagnostic in the Snipe sidebar — the AI explanation appears below it.

### Unit test

```bash
cd backend
python -m pytest explainer/test_explainer.py -v
```

---

## Cost Estimation (Gemini Free Tier)

As of early 2025, the Gemini API free tier provides:

| Model | Free requests/day | Free tokens/day |
|-------|------------------|----------------|
| gemini-2.5-flash | 1,500 | ~1 million |

Each Snipe explanation uses approximately:
- Input: ~250 tokens (prompt + code context)
- Output: ~150 tokens (explanation)

**At 400 tokens per request**, the free tier supports ~2,500 explanations per
day — far more than typical interactive development sessions require.

---

## Known Limitations

- **Latency:** Gemini Flash typically responds in 1–3 seconds.  During heavy
  typing sessions the explanation may lag behind the diagnostics.

- **Context window:** Code context is currently a raw string passed by the
  caller.  The AI model does not have access to the full file or import graph,
  so explanations for deeply nested issues may be less precise.

- **Language support:** Explanations are generated for all languages Snipe
  analyses (Python, C), but the model is not specialised for any one language.

- **Rate limiting:** If the free-tier quota is exhausted, the explainer returns
  `None` and the UI silently falls back to the raw diagnostic message.

- **No streaming:** Explanations are returned as a single response after the
  full generation completes.  Streaming is not currently implemented.
