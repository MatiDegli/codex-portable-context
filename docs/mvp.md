# Current Capabilities

## Goal

Provide a useful first version for reading, reviewing, and transporting Codex session context across devices without treating live local Codex state as a sync format.

## Current Exporter

Main command:

```bash
./scripts/codex-session-mirror
```

Useful variants:

```bash
./scripts/codex-session-mirror --redact
./scripts/codex-session-mirror --out-dir ./out-custom
./scripts/codex-session-mirror --conversation-only
./scripts/codex-session-mirror --no-context
./scripts/codex-session-mirror --no-tools
./scripts/codex-session-mirror --no-events
```

The exporter reads local session files from `~/.codex/sessions/**/*.jsonl` and writes a derived mirror under the chosen output directory.

## Current Outputs

The default mirror layout is:

- `out/README.md`
- `out/sessions-index.jsonl`
- `out/metadata/<session-id>.json`
- `out/sessions/<session-id>.md`
- `out/.codex-session-mirror-state.jsonl`

What each file is for:

- `README.md`
  Landing page for browsing the mirror directly after copy or sync.
- `sessions-index.jsonl`
  Combined machine-readable session index used by helper commands.
- `metadata/<session-id>.json`
  Per-session exported metadata, summary, and redaction report.
- `sessions/<session-id>.md`
  Readable transcript view of one exported session.
- `.codex-session-mirror-state.jsonl`
  Local bookkeeping for incremental export reuse inside the derived mirror.

## Reading Experience

The Markdown transcript view is optimized for useful review. It separates:

- session context
- user messages
- assistant messages
- tool calls
- tool outputs
- notable lifecycle events

Routine low-value records such as `token_count` and `turn_context` are omitted from Markdown so the output stays readable. This is a documented display choice only; raw source files remain unchanged.

The root `out/README.md` is generated from `sessions-index.jsonl`, lists sessions newest first, and links to the exported transcript and metadata files with relative paths.

## Redaction

Redaction is optional and affects only derived output.

Current placeholders include:

- `<redacted-user>`
- `<redacted-home>`
- `<redacted-host>`
- `<redacted-secret>`

Per-session metadata and index entries include `redaction_report`, which records whether redaction was enabled and the best-effort replacement counts seen in derived artifacts.

Redaction is helpful for transport, but it is not a guaranteed DLP system.

## Incremental Behavior

Repeated runs now reuse unchanged per-session derived outputs when possible.

The exporter currently:

- re-renders sessions whose source or export inputs changed
- rebuilds `sessions-index.jsonl`
- regenerates the root landing page
- removes stale derived session artifacts when source sessions disappear

## Helper Commands

The repo also includes lightweight helpers that operate only on the derived mirror:

- `scripts/codex-session-list`
- `scripts/codex-session-open`
- `scripts/codex-session-latest`

Supported convenience flags are intentionally small:

- `codex-session-list`: `--limit`, `--latest`, `--title`, `--id`, `--summary`, `--redaction`, `--json`
- `codex-session-open`: `--metadata`, `--print`, `--out-dir`, `--landing`, `--latest`
- `codex-session-latest`: `--metadata`, `--print`, `--out-dir`

These commands are convenience helpers only. They do not search raw Codex state, resume sessions, or add write-back behavior.

## Exported Index Contract

The helpers assume `sessions-index.jsonl` exposes at least:

- `session_id`
- `title`
- `updated_at`
- `session_timestamp`
- `metadata_relpath`
- `markdown_relpath`
- `summary.one_line`
- `redaction_report`

For older mirror outputs, helper path resolution can fall back to:

- `metadata/<session-id>.json`
- `sessions/<session-id>.md`

## Explicit Non-Goals

- no live bidirectional sync
- no write-back into `~/.codex`
- no dependency on a hosted backend
- no attempt to make raw sessions the sync format
- no credential copying
- no full-text search, semantic search, or resume subsystem
- no promise of perfect redaction or secret detection
