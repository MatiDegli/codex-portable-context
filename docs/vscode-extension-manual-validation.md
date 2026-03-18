# VS Code Extension Manual Validation

## Purpose

This checklist is the recommended first real validation pass for the thin VS Code extension.

It is intentionally manual and command-driven:

- no large UI work
- no extension-specific product logic
- no assumption that the extension replaces the Python CLI

The goal is to confirm that the current extension skeleton can:

- find the local Python tool
- run the documented commands
- open the expected artifacts
- fail clearly when setup is missing

## Recommended Validation Shape

Use two VS Code windows:

1. the main repo workspace
   - for the Python core and generated `out/` artifacts
2. the extension workspace
   - `extensions/vscode-codex-portable-context/`
   - for running the Extension Development Host

This keeps the extension isolated while still pointing it at the real repo.

## Prerequisites

From the repo root:

```bash
./scripts/bootstrap-python-v2
./scripts/validate-python-v2
```

Optional but useful before opening VS Code:

```bash
.venv/bin/codex-session-mirror --out-dir ./out
.venv/bin/codex-session-handoff --out-dir ./out --latest
```

## Extension Workspace Setup

Open `extensions/vscode-codex-portable-context/` in VS Code.

In workspace settings, set:

```json
{
  "codexPortableContext.workingDirectory": "../..",
  "codexPortableContext.outDir": "./out"
}
```

Why:

- `workingDirectory` resolves back to the repo root
- `outDir` then resolves to the repo's `./out`

If the extension cannot find the CLI automatically, set one of:

```json
{
  "codexPortableContext.commandDirectory": "../../.venv/bin"
}
```

or on Windows:

```json
{
  "codexPortableContext.commandDirectory": "..\\..\\.venv\\Scripts"
}
```

## Launching The Extension

Use the included launch configuration:

- `Run Codex Portable Context Extension`

This opens an Extension Development Host with the extension folder itself as the workspace, so the workspace-local `.vscode/settings.json` is available to the extension during the test run.

## Validation Checklist

### 1. Export Mirror

Run:

- `Codex Portable Context: Export Mirror`

Validate:

- the command succeeds
- the notification shows a sensible session count
- `Open Landing` opens `out/index.html`
- `Open Latest Reader` opens the latest session reader

### 2. Generate Handoff

Run:

- `Codex Portable Context: Generate Handoff`

Validate:

- the command succeeds
- the latest handoff Markdown opens
- the handoff includes:
  - `Current State`
  - `Continuity Entry`
  - `Open Loops / Risks`

### 3. Open Latest Reader

Run:

- `Codex Portable Context: Open Latest Reader`

Validate:

- the latest `reader/<session-id>.html` opens in the browser

### 4. Open Latest Handoff

Run:

- `Codex Portable Context: Open Latest Handoff`

Validate:

- the latest `handoffs/<session-id>.md` opens in the editor

### 5. Open Session Reader

Run:

- `Codex Portable Context: Open Session Reader`

Validate:

- a Quick Pick appears
- labels, preview lines, and activity/detail lines look sensible
- choosing a session opens the expected HTML reader

### 6. Open Session Markdown

Run:

- `Codex Portable Context: Open Session Markdown`

Validate:

- a Quick Pick appears
- choosing a session opens the expected transcript Markdown

## Negative Checks

These are important because the extension should fail clearly.

### Missing venv / CLI

Temporarily point `commandDirectory` at a bad path or open the extension without a bootstrapped environment.

Validate:

- the extension shows a clear actionable error
- the error points toward the documented bootstrap flow

### Empty Mirror

Point `outDir` at a missing or empty directory.

Validate:

- `Open Session Reader`
- `Open Session Markdown`
- `Open Latest Reader`
- `Open Latest Handoff`

all fail with useful messages instead of generic noise.

## Pass Criteria

The extension is manually ready enough for a first real-world pass when:

- all six main commands run successfully in a prepared workspace
- Quick Pick session selection is readable and correct
- export completion opens the generated reader index without guessing paths
- failure cases are understandable and actionable
- no provider-specific logic is duplicated in the extension

## Out Of Scope

This manual pass does not try to validate:

- packaging or marketplace publication
- tree views or webviews
- provider switching UI
- cross-device continuity flows from inside VS Code
- native Windows extension runtime from this Linux environment
