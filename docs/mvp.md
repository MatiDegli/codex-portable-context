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

It also now includes lightweight convenience helpers that read only the derived mirror:

- `scripts/codex-session-list`
- `scripts/codex-session-open`
- `scripts/codex-session-latest`

Supported convenience flags are intentionally small:

- `codex-session-list`: `--limit`, `--latest`, `--title`, `--id`, `--summary`, `--json`
- `codex-session-open`: `--metadata`, `--print`, `--out-dir`
- `codex-session-latest`: `--metadata`, `--print`, `--out-dir`

Markdown intentionally omits routine low-value records such as `token_count` and `turn_context`. This rule is conservative and documented so the export stays readable without pretending to be a lossless raw dump.

The new profile flags make the reading view more practical without changing the source of truth. They trim derived Markdown sections only.

Repeated runs now reuse unchanged per-session derived outputs when possible. The exporter still rebuilds the combined index and removes stale derived files when source sessions disappear.

The lookup helpers are convenience commands only. They do not search raw Codex state, they do not resume sessions, and they do not introduce any write-back behavior.

The exporter now also includes a small derived `summary` object in per-session metadata and in `sessions-index.jsonl`. It is mechanical rather than generative and is meant for quick scanning of recent sessions.

## Suggested First Outputs

- `out/sessions-index.jsonl`
- `out/metadata/<session-id>.json`
- `out/sessions/<session-id>.md`
- `out/.codex-session-mirror-state.jsonl`

These are now the concrete first outputs of the repo: stable, human-readable, and sync-friendlier than raw local state.

The lookup helpers assume `sessions-index.jsonl` exposes at least:

- `session_id`
- `title`
- `updated_at`
- `session_timestamp`
- `metadata_relpath`
- `markdown_relpath`
- `summary.one_line` for the optional summary view in `codex-session-list`

For older mirror outputs, helper path resolution falls back to `metadata/<session-id>.json` and `sessions/<session-id>.md`.

## Explicit Non-Goals For MVP

- no live bidirectional sync
- no write-back into `~/.codex`
- no dependency on a hosted backend
- no attempt to make raw sessions the sync format
- no credential copying
- no promise of perfect redaction or secret detection
- no full-text search, semantic search, or resume subsystem

## Future Extensions

- more selective redaction options
- safe transport recipes for Syncthing or `rsync`
- lightweight export polish that stays deterministic
