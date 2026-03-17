# Handoff Bundles

## Purpose

`codex-session-handoff` creates a small extractive bundle for continuity across devices without writing back into Codex state.

It is intentionally not a resume engine.

## What It Produces

For a selected exported session, the command writes:

- `handoffs/<session-id>.md`
- `handoffs/<session-id>.json`

inside the chosen derived mirror output directory.

## What It Uses

The handoff bundle starts from the derived mirror:

- `sessions-index.jsonl`
- `metadata/<session-id>.json`
- `sessions/<session-id>.md`
- `reader/<session-id>.html` when present

If the original local source session file is still available through `metadata.source_file`, the bundle also extracts:

- a compact current-state layer
- recent normalized actions
- a recent conversation window
- recent notable events
- recent tool activity

If the local source file is no longer available, the bundle still works, but it falls back to the derived mirror only.

## Why No LLM Is Needed

The handoff is extractive and deterministic:

- existing summary fields from the mirror
- exact timestamps and metadata
- recent blocks from the original parsed session when available
- no generated semantic summary

This keeps it auditable and avoids introducing API or model dependencies.

## Current Shape

The Markdown handoff is intentionally layered:

1. `Snapshot`
2. `Current State`
3. `Artifacts`
4. `Operator Note Template`
5. `Recent Actions (normalized)`
6. `Transcript Excerpt`
7. raw audit-trail sections

The top of the handoff is optimized for quick re-entry. The lower sections stay extractive and verbose on purpose for traceability.

## What It Is Good For

- moving work context from one device to another
- starting a fresh Codex session with a strong context package
- preserving a compact operator-oriented snapshot of a session

## What It Does Not Do

- it does not import anything into `~/.codex`
- it does not recreate a live session
- it does not guarantee a perfect semantic summary
- it does not replace reading the full transcript when details matter

`Current State` and `Recent Actions` are still heuristic and extractive. They are meant to improve operator speed, not to replace the full transcript when exact detail matters.

## Usage

Generate a handoff for the latest exported session:

```bash
codex-session-handoff --out-dir ./out --latest
```

Generate a handoff for a specific session prefix and print the Markdown path:

```bash
codex-session-handoff --out-dir ./out 019cef3a --print
```
