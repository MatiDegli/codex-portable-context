# codex-sync

Small local-first tooling scaffold for cross-device Codex session context.

The current direction is intentionally narrow: this repository is for a read-only mirror of local Codex sessions, not for syncing live mutable state or credentials between machines.

## Purpose

This project is meant to make Codex session history easier to preserve, inspect, search, and move across devices without treating `~/.codex` as a portable live database.

The source of truth stays local:

- local Codex state under `~/.codex`
- local session logs under `~/.codex/sessions`

The planned output is a separate derived mirror that is safer to read, copy, and index.

## Scope

Initial scope:

- scan local Codex session JSONL files
- extract safe and useful metadata
- generate a stable read-only mirror format
- support cross-device reading and context recovery
- keep credentials and mutable runtime state out of sync

Out of scope:

- syncing all of `~/.codex`
- syncing `auth.json`
- writing back into Codex session files
- treating internal Codex state as a stable public API
- concurrent bidirectional sync of live session state

## Design Principles

- local-first
- read-only mirror
- append-friendly exports
- explicit separation between source state and derived artifacts
- zero-credential-sync by default
- simple enough to inspect and self-host

## Repository Layout

```text
.
├── README.md
├── .gitignore
├── docs/
│   ├── architecture.md
│   ├── mvp.md
│   └── security.md
└── scripts/
```

## Planned MVP

The first useful version should:

1. Read `~/.codex/sessions/**/*.jsonl`.
2. Build a normalized per-session metadata record.
3. Export a read-only mirror format that is safer to sync than raw local state.
4. Avoid credentials, auth state, SQLite state, logs, and temporary files.

See:

- [architecture.md](docs/architecture.md)
- [security.md](docs/security.md)
- [mvp.md](docs/mvp.md)

## Status

This repository currently contains the structure and design brief only. No sync engine or parser has been implemented yet.
