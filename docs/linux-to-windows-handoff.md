# Linux-to-Windows Handoff

## Purpose

This workflow is for moving useful Codex work context from a Linux machine to a Windows machine without writing back into Codex state.

It uses only the derived mirror and optional handoff bundles.

## Validation Status

This is the expected workflow for the current Python-first implementation.

It is aligned with the existing Windows-native validation plan, but it should still be treated as a practical handoff guide until full native Windows validation is completed and recorded.

See [windows-native-validation.md](windows-native-validation.md) for the platform validation checklist.

## Recommendation

Keep the current commands explicit for now.

They are easier to validate across operating systems, and the generated reader under `out/index.html` is already the friendlier interface for the receiving machine.

## Source Linux Machine

From the repo root:

```bash
.venv/bin/codex-session-mirror --out-dir ./out
.venv/bin/codex-session-handoff --out-dir ./out --latest
```

For a less-trusted receiving machine, prefer a redacted export:

```bash
.venv/bin/codex-session-mirror --out-dir ./out-redacted --redact
.venv/bin/codex-session-handoff --out-dir ./out-redacted --latest
```

Useful checks before transport:

```bash
.venv/bin/codex-session-list --out-dir ./out --latest --summary --details
.venv/bin/codex-session-open --out-dir ./out --latest --reader --print
.venv/bin/codex-session-open --out-dir ./out --latest --handoff --print
```

## Transport

Copy the derived mirror directory only.

Examples:

```bash
rsync -a ./out/ /run/media/$USER/TRANSFER/codex-portable-context/out/
```

```bash
rsync -a ./out-redacted/ /run/media/$USER/TRANSFER/codex-portable-context/out-redacted/
```

Do not transport:

- `~/.codex/`
- `auth.json`
- SQLite state
- logs, `tmp`, or shell snapshots

## Receiving Windows Machine

The receiving Windows machine does not need the source `~/.codex` session files just to read the handoff.

You can browse the transported mirror directly:

```powershell
py -m webbrowser C:\path\to\codex-portable-context\out\index.html
```

Or open the extracted handoff bundle directly:

```powershell
notepad C:\path\to\codex-portable-context\out\handoffs\<session-id>.md
```

If the repo is also available on the receiving machine, the Python helpers should work against the transported mirror:

```powershell
.venv\Scripts\codex-session-list.exe --out-dir C:\path\to\codex-portable-context\out --latest --summary --details
.venv\Scripts\codex-session-open.exe --out-dir C:\path\to\codex-portable-context\out --latest --reader
.venv\Scripts\codex-session-open.exe --out-dir C:\path\to\codex-portable-context\out --latest --handoff
```

If the installed `.exe` entrypoints are not available, use the module form instead:

```powershell
.venv\Scripts\python -m codex_portable_context.cli.list --out-dir C:\path\to\codex-portable-context\out --latest --summary --details
.venv\Scripts\python -m codex_portable_context.cli.open --out-dir C:\path\to\codex-portable-context\out --latest --reader
```

## What This Gives You

- a portable mirror landing page
- browser-based reading through `index.html`
- handoff bundles for focused continuity
- no write-back into the receiving machine's live Codex state

## What It Does Not Give You

- live session resume
- import into the receiving machine's `~/.codex`
- a guarantee that every Windows-native edge case has already been validated

If you need to continue work, use the handoff bundle and transcript as the starting context for a new session on the Windows machine.
