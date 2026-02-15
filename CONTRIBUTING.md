# Contributing to Snipe

Thank you for considering contributing to Snipe. This document outlines expectations and workflow so contributions are smooth and consistent.

---

## Code of conduct

- Be respectful and constructive in discussions, issues, and pull requests.
- Focus on the code and ideas, not on individuals.

---

## How to contribute

- **Bug reports & feature requests:** Open an [Issue](../../issues) with a clear title and description.
- **Code or docs:** Open a **Pull Request (PR)** against the default branch. Do **not** push directly to `main`; all changes go through review.

---

## Branch and merge policy

- **`main`** is the default branch and should stay stable.
- **Do not merge directly into `main`.** All changes must go through a Pull Request.
- Create a branch for your work (e.g. `fix/array-bounds-false-positive`, `feat/python-type-hints`, `docs/readme-quickstart`).
- PRs require at least **one approval** from a maintainer before merge, unless the project explicitly states otherwise.
- Keep PRs focused: one logical change per PR when possible.

---

## Pull requests

### Before opening a PR

- Ensure the backend and extension still work (see [README Quick Start](README.md#quick-start)).
- If you change backend logic, run: `cd backend && python -m pytest ../tests/ -v` (or the project’s test command).
- Rebase or merge the latest `main` into your branch and fix any conflicts.

### PR title and description

- **Title:** Short and descriptive (e.g. `Fix C array size extraction for declarators`, `Add CONTRIBUTING and MIT license`).
- **Description:** Include:
  - **What** changed and **why** (problem or goal).
  - **How** it was addressed (high-level approach).
  - Any breaking changes or follow-up work.
  - How you tested (manual steps and/or tests).

### Review

- Address review comments in new commits or by amending, and keep the conversation professional.

---

## Issues

- Use a **clear, concise title** (e.g. `Array bounds not reported when size in separate file`).
- In the description, include:
  - Steps to reproduce (and sample code/repo layout if relevant).
  - Expected vs actual behavior.
  - Environment (OS, Python/Node versions, VSCode/Cursor version) if it might matter.

---

## Commit messages

- Keep messages **short and concise**.
- Use the **imperative mood** (“Add feature”, “Fix crash”, not “Added feature” / “Fixes crash”).
- Optionally prefix with scope: `parser: fix array size from declarator`, `extension: show diagnostics for unsaved file`.

**Examples:**

- `Fix C array size extraction for declarator size field`
- `extension: reload instructions in README`
- `Add CONTRIBUTING.md and MIT LICENSE`

---

## Code style and comments

- **Comments:** Explain *why* when it’s not obvious from the code; avoid restating what the code does in one line.
- **Docstrings:** Use for public functions, classes, and modules (backend and extension) so behavior is clear.
- Follow existing style in the file (indentation, naming, imports). The project uses Python in the backend and TypeScript in the extension.

---

## Project structure (quick reference)

- **Backend:** `backend/` (FastAPI server, parsers, analyzers, graph).
- **Extension:** `extension/` (VSCode/Cursor plugin).
- **Tests:** `tests/` (e.g. `unit_tests.py`).
- **Docs:** `README.md`, `CONTRIBUTING.md`, and any SDP/SRS or design docs in the repo.

---

## Questions

If something is unclear, open an Issue with the “question” label or ask in the PR description. We’re happy to clarify expectations or workflow.

Thank you for contributing to Snipe.
