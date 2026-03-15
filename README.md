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
    ├── codex-session-list
    ├── codex-session-latest
    ├── codex-session-mirror
    ├── codex-session-open
    └── libcodex-session.sh
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
├── .codex-session-mirror-state.jsonl
├── sessions-index.jsonl
├── metadata/
│   └── <session-id>.json
└── sessions/
    └── <session-id>.md
```

This output is read-only derived data for browsing and context recovery. It is not meant to be written back into Codex state.

Repeated runs reuse unchanged per-session exports when possible. The hidden state file in `out/` is local bookkeeping for the derived mirror, not part of Codex source state.

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

Conversation-focused export:

```bash
./scripts/codex-session-mirror --conversation-only
```

Custom section filtering:

```bash
./scripts/codex-session-mirror --no-context --no-events
./scripts/codex-session-mirror --no-tools
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

## Export Profiles

The default export remains the full reading-oriented mirror.

Optional flags can trim sections from the Markdown export:

- `--no-context`
- `--no-tools`
- `--no-events`
- `--conversation-only`

These flags do not modify source session files, and they do not turn the tool into a sync or resume engine. They only control how much of the derived Markdown view is emitted.

## Incremental Export

The exporter now reuses unchanged per-session artifacts by default.

On each run it:

- checks whether a session input still matches the last exported fingerprint
- re-renders only sessions whose source or export-relevant inputs changed
- rebuilds `sessions-index.jsonl` from the current derived outputs
- removes stale per-session mirror files when source sessions disappear or their session ids change

This keeps the mirror read-only with respect to `~/.codex` while making repeated exports much cheaper.

## Lookup Helpers

The repo now includes small convenience CLIs that operate only on the derived mirror under `out/`.

- `./scripts/codex-session-list`
  Lists exported sessions from `out/sessions-index.jsonl`.
  Useful flags: `--limit`, `--latest`, `--title`, `--id`, `--json`.
- `./scripts/codex-session-open <session-id-or-prefix>`
  Opens the derived Markdown export for one exported session.
  Useful flags: `--metadata`, `--print`, `--out-dir`.
- `./scripts/codex-session-latest`
  Opens the latest exported session.
  Useful flags: `--metadata`, `--print`, `--out-dir`.

These helpers are intentionally narrow. They are not a search engine, resume engine, or sync subsystem.

Examples:

```bash
./scripts/codex-session-list --latest
./scripts/codex-session-list --title galaxy --limit 5
./scripts/codex-session-open 019cef3a --print
./scripts/codex-session-open --metadata 019cef3a --print
./scripts/codex-session-latest --print
./scripts/codex-session-latest --metadata --print
```

## Index Contract

The lookup helpers read only the exported mirror index:

- `out/sessions-index.jsonl`

They currently rely on these exported fields:

- `session_id`
- `title`
- `updated_at`
- `session_timestamp`
- `metadata_relpath`
- `markdown_relpath`

For compatibility with older mirror outputs, the helpers can fall back to:

- `metadata/<session-id>.json`
- `sessions/<session-id>.md`

That fallback is only for path resolution. The helpers still operate exclusively on derived files under `out/`.

## Planned Follow-Up

The next useful steps are still:

1. Improve the normalized per-session metadata record further.
2. Add optional redaction refinements without becoming a DLP system.
3. Add transport recipes without touching credentials.
4. Keep the convenience helpers small and explicit instead of growing them into a search or resume layer.

See:

- [architecture.md](docs/architecture.md)
- [security.md](docs/security.md)
- [mvp.md](docs/mvp.md)

## Status

This repository now contains the first read-only export command plus the design brief for the next iterations.
