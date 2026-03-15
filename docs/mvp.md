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

It currently exports:

- a per-session metadata JSON file
- a combined JSONL index
- a Markdown transcript view built from user and assistant messages

## Suggested First Outputs

- `out/sessions-index.jsonl`
- `out/metadata/<session-id>.json`
- `out/sessions/<session-id>.md`

These are now the concrete first outputs of the repo: stable, human-readable, and sync-friendlier than raw local state.

## Explicit Non-Goals For MVP

- no live bidirectional sync
- no write-back into `~/.codex`
- no dependency on a hosted backend
- no attempt to make raw sessions the sync format
- no credential copying

## Future Extensions

- incremental scans
- redaction options
- summary generation
- safe transport recipes for Syncthing or `rsync`
- session lookup helpers
