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

## Extension-Facing CLI Contract

The intended stable integration surface is:

- `codex-session-mirror --json`
- `codex-session-list --json`
- `codex-session-open --print`
- `codex-session-handoff --latest --print`

The current `Export Mirror` command already consumes `codex-session-mirror --json` so it can show a cleaner completion message and open the generated reader index without guessing paths.

See:

- [list-json-contract.md](../../docs/integrations/list-json-contract.md)
- [extension-invocation-contract.md](../../docs/integrations/extension-invocation-contract.md)

Recommended path during development:

- open the repo in VS Code
- bootstrap the local `.venv`
- use the extension commands against the same workspace

For a first real manual pass in VS Code, see:

- [vscode-extension-manual-validation.md](../../docs/integrations/vscode-extension-manual-validation.md)

The extension folder also includes a minimal launch configuration for running an Extension Development Host:

- `.vscode/launch.json`

That launch config opens the extension folder itself as the host workspace, so the workspace-local `.vscode/settings.json` is actually visible to the running extension.

Recommended local bootstrap:

- Linux:
  - `./scripts/bootstrap-python-v2`
- Windows PowerShell:
  - `py -3.13 -m venv .venv`
  - `.venv\Scripts\python -m pip install -e ".[dev]"`

Configured `commandDirectory` and `pythonPath` are resolved flexibly:

- first relative to the extension workspace root
- then relative to `codexPortableContext.workingDirectory`

That means both workspace-relative values like `../../.venv/bin` and repo-relative values like `./.venv/bin` can work, depending on how you launch the Extension Development Host.

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
