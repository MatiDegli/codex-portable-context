# codex-portable-context

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
    └── codex-session-mirror
```

## Current MVP

The repository now includes a first local export command:

```bash
./scripts/codex-session-mirror
```

By default it reads:

- `~/.codex/sessions/**/*.jsonl`
- `~/.codex/session_index.jsonl` when available

And writes a derived mirror under:

```text
out/
├── sessions-index.jsonl
├── metadata/
│   └── <session-id>.json
└── sessions/
    └── <session-id>.md
```

This output is read-only derived data for browsing and context recovery. It is not meant to be written back into Codex state.

## Export Quality

The current export is optimized for useful reading, not raw event dumping.

The Markdown output now separates:

- session context
- user messages
- assistant messages
- tool calls
- tool outputs
- notable lifecycle events

To keep the export readable, routine noise such as `token_count` and `turn_context` records is omitted from Markdown. The raw session source remains untouched and is still the authoritative input.

## Redaction

Redaction is optional and only affects the derived mirror output.

Default behavior is non-redacted:

```bash
./scripts/codex-session-mirror
```

Redacted export:

```bash
./scripts/codex-session-mirror --redact
```

When redaction is enabled, the script uses conservative placeholders such as:

- `<redacted-user>`
- `<redacted-home>`
- `<redacted-host>`
- `<redacted-secret>`

This is best-effort redaction, not a guaranteed DLP system. Source session files under `~/.codex/sessions` are never modified.

## Usage

Default export:

```bash
./scripts/codex-session-mirror
```

Redacted export:

```bash
./scripts/codex-session-mirror --redact
```

Custom paths:

```bash
./scripts/codex-session-mirror \
  --codex-home "$HOME/.codex" \
  --out-dir ./out
```

Custom redacted output path:

```bash
./scripts/codex-session-mirror \
  --redact \
  --out-dir ./out-redacted
```

## Planned Follow-Up

The next useful steps are still:

1. Read `~/.codex/sessions/**/*.jsonl`.
2. Improve the normalized per-session metadata record further.
3. Add optional redaction refinements without becoming a DLP system.
4. Add transport recipes without touching credentials.

See:

- [architecture.md](docs/architecture.md)
- [security.md](docs/security.md)
- [mvp.md](docs/mvp.md)

## Status

This repository now contains the first read-only export command plus the design brief for the next iterations.
