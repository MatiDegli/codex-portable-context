# Codex Portable Context VS Code Extension

This directory contains a minimal VS Code extension skeleton for `codex-portable-context`.

It is intentionally thin:

- it invokes the Python CLI
- it opens generated artifacts
- it does not duplicate mirror, handoff, summary, or reader logic

## Current Commands

- `Codex Portable Context: Export Mirror`
- `Codex Portable Context: Generate Handoff`
- `Codex Portable Context: Open Latest Reader`
- `Codex Portable Context: Open Latest Handoff`
- `Codex Portable Context: Open Session Reader`
- `Codex Portable Context: Open Session Markdown`

## Current Assumptions

The extension looks for the tool in this order:

1. `codexPortableContext.commandDirectory`
2. workspace-local `.venv` entrypoints
3. `codexPortableContext.pythonPath`
4. workspace-local `.venv` Python module fallback
5. command name on `PATH`

Recommended path during development:

- open the repo in VS Code
- bootstrap the local `.venv`
- use the extension commands against the same workspace

## Settings

- `codexPortableContext.workingDirectory`
- `codexPortableContext.outDir`
- `codexPortableContext.commandDirectory`
- `codexPortableContext.pythonPath`
- `codexPortableContext.preferRedactedExport`

## Scope Discipline

This skeleton is intentionally small.

It should remain:

- a frontend
- command-driven
- cross-platform
- dependent on the Python CLI as the system of record
