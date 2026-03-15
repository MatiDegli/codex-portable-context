# MVP

## Goal

Build a first version that is useful for reading and context recovery across devices, without trying to resume or synchronize live mutable Codex state.

## MVP Requirements

- scan `~/.codex/sessions/**/*.jsonl`
- identify sessions and basic metadata
- export a normalized read-only mirror
- keep raw source and exported mirror clearly separate
- exclude credentials and runtime state

## Suggested First Outputs

- `out/sessions-index.jsonl`
- `out/metadata/<session-id>.json`
- `out/sessions/<session-id>.md`

These are placeholders for now, but they reflect the intended direction: stable, human-readable, and sync-friendlier than raw local state.

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
