# VS Code Extension Strategy

## Decision

The VS Code extension should be a thin frontend for the existing Python-first core.

It should not become a second implementation of:

- session discovery
- mirror generation
- handoff generation
- summary derivation
- reader generation
- redaction
- session resolution

Those responsibilities remain in the Python package under `src/codex_portable_context/`.

## Why the Python Core Remains Primary

`codex-portable-context` is already designed as:

- local-first
- read-only with respect to `~/.codex`
- cross-platform
- usable outside VS Code
- centered on derived artifacts, not editor state

That architecture should not change.

The extension should exist to reduce friction for developers who already live in VS Code, not to replace the CLI or make the product editor-dependent.

Reasons to keep Python primary:

- one implementation path across Linux and Windows
- one mirror and handoff contract
- one validation surface
- continued usability outside VS Code
- less long-term maintenance than duplicating artifact logic in TypeScript

## Responsibility Split

### Python Core Responsibilities

The Python core owns:

- discovery of raw Codex session files
- parsing of source session logs
- mirror generation
- handoff generation
- summary derivation
- reader generation
- redaction
- index loading and session lookup
- open-target resolution
- exit codes and artifact-level behavior

### VS Code Extension Responsibilities

The extension should own:

- command palette actions
- lightweight Quick Pick flows
- detection of the current workspace
- invoking the Python CLI with the right arguments
- opening generated artifacts in the editor or browser
- presenting actionable setup errors when the CLI is unavailable

### Explicit Non-Goals For The Extension

Do not implement these in the extension:

- raw session parsing
- mirror or handoff generation logic
- a second copy of the reader renderer
- sync or transport logic
- resume or write-back behavior
- a daemon, service, or backend
- a large custom webview UI in the first version

## Minimum Useful Extension Scope

The first extension version should stay small and command-driven.

Recommended commands:

1. `Codex Portable Context: Export Mirror`
   Python CLI:
   `codex-session-mirror`
   Recommended flags:
   `--out-dir <workspace-default-or-user-setting>`
   Optional quick choice:
   standard or `--redact`
   Result:
   show completion and offer to open the landing page or reader

2. `Codex Portable Context: Generate Handoff`
   Python CLI:
   `codex-session-handoff`
   Recommended flags:
   `--out-dir <workspace-default-or-user-setting> --latest`
   Result:
   open the generated handoff Markdown

3. `Codex Portable Context: Open Latest Reader`
   Python CLI:
   `codex-session-open`
   Recommended flags:
   `--out-dir <workspace-default-or-user-setting> --latest --reader --print`
   Result:
   open the returned HTML path

4. `Codex Portable Context: Open Latest Handoff`
   Python CLI:
   `codex-session-open`
   Recommended flags:
   `--out-dir <workspace-default-or-user-setting> --latest --handoff --print`
   Result:
   open the returned Markdown path

5. `Codex Portable Context: Open Session Reader`
   Python CLI sequence:
   `codex-session-list --out-dir <...> --json`
   then
   `codex-session-open --out-dir <...> <session-id> --reader --print`
   Result:
   Quick Pick a session, then open the returned reader HTML

6. `Codex Portable Context: Open Session Markdown`
   Python CLI sequence:
   `codex-session-list --out-dir <...> --json`
   then
   `codex-session-open --out-dir <...> <session-id> --print`
   Result:
   Quick Pick a session, then open the returned transcript Markdown

These commands are enough to make the project feel integrated in VS Code without moving product logic into the editor.

## Recommended UX For v1

Use only these surfaces at first:

- Command Palette commands
- a small Quick Pick for choosing standard vs redacted export
- a small Quick Pick for choosing a session from `codex-session-list --json`
- normal editor/browser opening of generated files

Why this should stay small:

- the core value is in the artifacts, not in extension chrome
- the CLI already does the heavy lifting
- command-based UX is easier to keep cross-platform and maintainable
- it avoids building a second app inside VS Code too early

## Later Optional UX Phases

Only after the thin command path feels stable:

- a lightweight tree view of exported sessions
- buttons for "latest reader" and "latest handoff"
- workspace settings for default `out-dir` and redaction preference

Still avoid:

- custom webview dashboards
- embedded re-rendering of mirror artifacts
- editor-only flows that bypass the Python CLI

## Extension-Readiness Review Of The Current CLI

The current CLI surface is already close to extension-ready.

Useful capabilities already present:

- `codex-session-mirror --out-dir`
- `codex-session-mirror --redact`
- `codex-session-list --json`
- `codex-session-list --latest`
- `codex-session-open --latest`
- `codex-session-open --reader`
- `codex-session-open --handoff`
- `codex-session-open --print`
- session-id or unique-prefix selection
- non-zero exits for invalid combinations and missing results

### No-Regret Gaps To Track

These are small ergonomics gaps worth tracking before or during extension work:

1. A documented stable machine-readable contract for `codex-session-list --json`
   Why:
   the extension will likely use it for Quick Pick session selection

2. A small documented extension-facing invocation contract
   Why:
   the extension should rely on a tiny, explicit set of CLI behaviors rather than informal assumptions

3. A machine-readable success output for `codex-session-mirror`
   Why:
   it makes completion messaging and open-after-export flows cleaner

These are intentionally small. None of them justify moving logic out of Python.

The first two of these are now captured in:

- [list-json-contract.md](list-json-contract.md)
- [extension-invocation-contract.md](extension-invocation-contract.md)

The third is now available through:

- `codex-session-mirror --json`

## Cross-Platform Invocation Strategy

The extension should try Python-first invocation in this order:

1. configured command path from extension settings, if present
2. workspace-local virtual environment entrypoint
3. configured Python interpreter fallback, if present
4. workspace-local module fallback through the venv interpreter
5. command name on `PATH` as a last-resort compatibility fallback

Practical examples:

- Linux:
  - `.venv/bin/codex-session-mirror`
  - `.venv/bin/python -m codex_portable_context.cli.mirror`
- Windows:
  - `.venv\\Scripts\\codex-session-mirror.exe`
  - `.venv\\Scripts\\python.exe -m codex_portable_context.cli.mirror`

If the tool is not installed yet, the extension should:

- fail clearly
- explain the expected bootstrap step
- offer the exact repo-local setup command from the docs

Example actionable guidance:

- Linux:
  `./scripts/bootstrap-python-v2`
- Windows:
  `py -3.13 -m venv .venv`
  then
  `.venv\Scripts\python -m pip install -e ".[dev]"`

## Error Handling Expectations

The extension should surface CLI failures as actionable messages, not generic "task failed" noise.

At minimum, handle:

- CLI not found
- venv missing
- invalid argument combination
- no exported sessions available
- selected session not found
- mirror not generated yet

The extension should prefer showing the original CLI stderr with a short extension-specific hint rather than rewriting errors aggressively.

## Smallest Practical Roadmap

### Phase 1

- publish the strategy
- keep Python CLI as the source of truth
- optionally tighten any tiny CLI docs needed for extension integration

### Phase 2

- build a minimal extension with only command palette actions
- invoke the Python CLI from the workspace venv
- support export, latest reader, latest handoff, and session Quick Pick opens

### Phase 3

- add only small UX polish based on real use
- consider a simple session tree only if the command-based flow proves too limiting

## Recommendation

Build the extension as a thin orchestration layer on top of the current Python CLI.

That gives developers a smoother in-editor workflow while preserving the architecture that already makes the project portable, testable, and cross-platform.

## Current Repo Status

The repo now includes an initial extension skeleton under:

- `extensions/vscode-codex-portable-context/`

It is intentionally minimal:

- manifest plus command contributions
- a single JS extension entrypoint
- no mirror or handoff logic duplicated from Python
- no build step required for the first local iteration
