# MVP

## Goal

Build a first version that is useful for reading and context recovery across devices, without trying to resume or synchronize live mutable Codex state.

## MVP Requirements

- scan `~/.codex/sessions/**/*.jsonl`
- identify sessions and basic metadata
- export a normalized read-only mirror
- keep raw source and exported mirror clearly separate
- exclude credentials and runtime state

## Current Command

The initial command is:

```bash
./scripts/codex-session-mirror
```

Redacted mode:

```bash
./scripts/codex-session-mirror --redact
```

Custom output directory:

```bash
./scripts/codex-session-mirror --out-dir ./out-custom
```

Conversation-focused export:

```bash
./scripts/codex-session-mirror --conversation-only
```

Section filtering:

```bash
./scripts/codex-session-mirror --no-context
./scripts/codex-session-mirror --no-tools
./scripts/codex-session-mirror --no-events
```

It currently exports:

- a local state file for incremental derived export reuse
- a per-session metadata JSON file
- a combined JSONL index
- a Markdown transcript view with clearer separation between context, user messages, assistant messages, tool calls, tool outputs, and notable events

Markdown intentionally omits routine low-value records such as `token_count` and `turn_context`. This rule is conservative and documented so the export stays readable without pretending to be a lossless raw dump.

The new profile flags make the reading view more practical without changing the source of truth. They trim derived Markdown sections only.

Repeated runs now reuse unchanged per-session derived outputs when possible. The exporter still rebuilds the combined index and removes stale derived files when source sessions disappear.

## Suggested First Outputs

- `out/sessions-index.jsonl`
- `out/metadata/<session-id>.json`
- `out/sessions/<session-id>.md`
- `out/.codex-session-mirror-state.jsonl`

These are now the concrete first outputs of the repo: stable, human-readable, and sync-friendlier than raw local state.

## Explicit Non-Goals For MVP

- no live bidirectional sync
- no write-back into `~/.codex`
- no dependency on a hosted backend
- no attempt to make raw sessions the sync format
- no credential copying
- no promise of perfect redaction or secret detection

## Future Extensions

- more selective redaction options
- summary generation
- safe transport recipes for Syncthing or `rsync`
- session lookup helpers
