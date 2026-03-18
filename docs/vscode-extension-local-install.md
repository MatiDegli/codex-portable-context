# VS Code Extension Local Install

## Purpose

This guide explains how to package and install the thin `codex-portable-context` VS Code extension locally as a `.vsix`, without publishing to the Marketplace.

This is the next step after the manual Extension Development Host validation passes.

## Current Status

The extension is not published to the Marketplace.

The repo now includes the minimum packaging readiness pieces for local installation:

- extension manifest with a publisher id
- `.vscodeignore`
- thin CLI-first architecture and documented integration contract

This repo does **not** currently bundle Node tooling, and this Linux environment did not have `node`, `npm`, or `npx` available when this guide was written.

## Prerequisites

You need a machine with:

- VS Code
- Node.js
- npm or npx

The Python project environment should already be bootstrapped in the repo:

```bash
cd ~/Projects/codex-sync
./scripts/bootstrap-python-v2
```

## Package The Extension

From the extension directory:

```bash
cd ~/Projects/codex-sync/extensions/vscode-codex-portable-context
npx @vscode/vsce package
```

Expected result:

- a `.vsix` file appears in the extension directory

Typical filename:

```text
codex-portable-context-vscode-0.1.0.vsix
```

## Install The `.vsix`

In VS Code:

1. open the Extensions view
2. open the `...` menu
3. choose `Install from VSIX...`
4. select the generated `.vsix`

Or from the command line if `code` is available:

```bash
code --install-extension ~/Projects/codex-sync/extensions/vscode-codex-portable-context/codex-portable-context-vscode-0.1.0.vsix
```

## First Configuration After Install

The installed extension still needs to know where the Python CLI lives.

The most reliable first setup is to configure these settings with absolute paths:

```json
{
  "codexPortableContext.workingDirectory": "/home/matidegli/Projects/codex-sync",
  "codexPortableContext.outDir": "/home/matidegli/Projects/codex-sync/out",
  "codexPortableContext.commandDirectory": "/home/matidegli/Projects/codex-sync/.venv/bin"
}
```

On Windows, point `commandDirectory` at `.venv\\Scripts`.

## Recommended Post-Install Checks

After install, verify:

- `Codex Portable Context: Export Mirror`
- `Codex Portable Context: Open Latest Reader`
- `Codex Portable Context: Generate Handoff`
- `Codex Portable Context: Open Latest Handoff`

If those work, the installed extension is already providing the intended thin frontend value.

## Notes

- This is a local install flow only.
- It does not imply Marketplace publication.
- The extension should remain a frontend over the Python CLI, not a second implementation.
