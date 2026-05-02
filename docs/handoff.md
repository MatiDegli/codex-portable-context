# Handoff Bundles

## Purpose

`codex-session-handoff` creates a small extractive bundle for continuity across devices without writing back into Codex state.

It is intentionally not a resume engine.

For the roadmap that moves handoffs toward stronger fresh-session re-entry, see [Continuity Bridge Roadmap](./continuity-bridge-roadmap.md).

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

- a continuation brief for fresh-session re-entry
- a resolved-state layer that separates latest request from resolution status
- a contextual request field for short follow-ups such as `Pasamelo`
- changed/key artifact paths from recent text, tool outputs, and git status
- durable decisions, invariants, rejected paths, and open architecture questions
- a re-entry posture contract that defaults the first turn to read-only review
- a copy-ready restart prompt for a fresh local session
- a compact current-state layer
- explicit compaction summaries or prompts when provider events expose them
- linked child session summaries from local thread state when available
- recent normalized actions
- a recent conversation window
- recent notable events
- recent tool activity

Child session enrichment reads `state_5.sqlite` through Python's built-in SQLite support. The `sqlite3` command-line tool is not required, and missing local SQLite state degrades to an empty child-session section.

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
2. `Continuation Brief`
3. `Resolved State`
4. `Changed / Key Artifacts`
5. `Decisions / Invariants`
6. `Re-Entry Posture`
7. `Restart Prompt`
8. `Current State`
9. `Continuity Entry`
10. `Artifacts`
11. `Operator Note Template`
12. `Compaction Summaries` when available
13. `Linked Child Sessions` when available
14. `Recent Actions (normalized)`
15. `Open Loops / Risks`
16. `Transcript Excerpt`
17. raw audit-trail sections

The top of the handoff is optimized for quick re-entry. The lower sections stay extractive and verbose on purpose for traceability.

## What It Is Good For

- moving work context from one device to another
- starting a fresh Codex session with a strong context package
- preserving a compact operator-oriented snapshot of a session

For the exact minimum cross-device package expected on the destination machine, see [Codex Continuity Bundle](./codex-continuity-bundle.md).

## What It Does Not Do

- it does not import anything into `~/.codex`
- it does not recreate a live session
- it does not guarantee a perfect semantic summary
- it does not replace reading the full transcript when details matter

`Continuation Brief`, `Resolved State`, `Current State`, and `Recent Actions` are still heuristic and extractive. They are meant to improve operator speed, not to replace the full transcript when exact detail matters.

`Open Loops / Risks` follows the same rule: it only surfaces conservative signals such as missing validation, obvious recent failures, open questions that are explicit in the user text, and operational risks like missing local source or a dirty repo.

The current continuity bridge layer provides a compact, traceable re-entry brief with resolved state, durable decisions, changed artifacts, re-entry posture, and a copy-ready restart prompt. Remaining improvements are tracked in [Continuity Bridge Roadmap](./continuity-bridge-roadmap.md).

When `codex-session-handoff` runs, it also refreshes the per-session reader HTML with an embedded restart prompt and a copy button. If a browser blocks clipboard writes from a local `file://` page, the prompt text remains selected for manual copy.

## Usage

Generate a handoff for the latest exported session:

```bash
codex-session-handoff --out-dir ./out --latest
```

Generate a handoff for a specific session prefix and print the Markdown path:

```bash
codex-session-handoff --out-dir ./out 019cef3a --print
```

Print only the generated fresh-session restart prompt:

```bash
codex-session-handoff --out-dir ./out 019cef3a --restart-prompt
```

Audit recent handoff memory quality:

```bash
codex-session-handoff-audit --out-dir ./out --limit 20
```

The audit command regenerates selected handoffs by default, then reports whether `Decisions / Invariants` has useful memory, which sources contributed, and which sessions are `no_memory` or `low_confidence`. Use `--no-generate` to inspect existing handoff JSON files only, or `--json` for machine-readable output.

Generate a manual-only restart prompt E2E manifest:

```bash
codex-session-handoff-audit --out-dir ./out \
  --write-e2e-manifest ./out/restart-prompt-e2e.json \
  019dcbe0 019dde52 019ddb37 019de39e
```

The E2E manifest writes prompts and a result rubric, but it does not launch
agents or send messages. See [Restart Prompt E2E Protocol](./restart-prompt-e2e.md).
