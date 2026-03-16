# Linux-to-Linux Handoff

## Purpose

This workflow is for moving useful Codex work context from one Linux machine to another without writing back into `~/.codex`.

It uses the derived mirror and optional handoff bundles only.

## Recommendation

Use the current commands as they are for now.

They are explicit, stable, and easy to validate. The static reader under `out/index.html` is already the more user-friendly layer for browsing on the receiving device, so there is no strong need to add more command shortcuts before the interface settles further.

## Source Machine

From the repo root:

```bash
.venv/bin/codex-session-mirror --out-dir ./out
.venv/bin/codex-session-handoff --out-dir ./out --latest
```

If you want a safer transport target for a less-trusted device, generate a redacted mirror instead:

```bash
.venv/bin/codex-session-mirror --out-dir ./out-redacted --redact
.venv/bin/codex-session-handoff --out-dir ./out-redacted --latest
```

Useful checks before transport:

```bash
.venv/bin/codex-session-list --out-dir ./out --latest --summary --details
.venv/bin/codex-session-open --out-dir ./out --latest --handoff --print
.venv/bin/codex-session-open --out-dir ./out --latest --reader --print
```

## Transport

Copy the derived mirror directory only.

Examples:

```bash
rsync -a ./out/ user@other-linux-box:~/codex-portable-context/inbox/out/
```

```bash
rsync -a ./out-redacted/ /mnt/external-drive/codex-portable-context/out-redacted/
```

Do not transport:

- `~/.codex/`
- `auth.json`
- SQLite state
- logs, `tmp`, or shell snapshots

## Receiving Machine

The receiving Linux machine does not need the source `~/.codex` session files just to read the handoff.

You can browse the transported mirror directly:

```bash
python -m webbrowser ~/codex-portable-context/inbox/out/index.html
```

Or open the extracted handoff bundle directly:

```bash
less ~/codex-portable-context/inbox/out/handoffs/<session-id>.md
```

If the repo is also available on the receiving machine, the existing helpers still work against the transported mirror:

```bash
.venv/bin/codex-session-list --out-dir ~/codex-portable-context/inbox/out --latest --summary --details
.venv/bin/codex-session-open --out-dir ~/codex-portable-context/inbox/out --latest --reader
.venv/bin/codex-session-open --out-dir ~/codex-portable-context/inbox/out --latest --handoff
```

## What This Gives You

- a readable mirror landing page
- per-session transcript and metadata
- a smaller handoff bundle for continuity
- no write-back into live Codex state

## What It Does Not Give You

- live session resume
- import into another machine's `~/.codex`
- perfect semantic summarization

If you need to continue work, use the handoff bundle and transcript as the starting context for a new session on the receiving machine.
