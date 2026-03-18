# Architecture

## Intent

This project is a read-only mirror layer for Codex sessions.

It should treat local Codex session files as an input source, not as a format to mutate, merge, or own.

## Core Model

There are three separate layers:

1. Local sensitive state
2. Local raw session source
3. Derived mirror output

### 1. Local Sensitive State

Examples:

- `~/.codex/auth.json`
- `~/.codex/config.toml`
- local SQLite state
- local logs and caches

This layer stays local and is not part of the mirror.

### 2. Local Raw Session Source

Primary source:

- `~/.codex/sessions/**/*.jsonl`

This layer is the local input. It may be inspected and parsed, but should not be rewritten by this project.

### 3. Derived Mirror Output

This is the stable export produced by this project for reading, indexing, and cross-device context.

The exact format is still open, but the expected shape is something like:

- `.codex-session-mirror-state.jsonl`
- `sessions-index.jsonl`
- `metadata/<session-id>.json`
- `sessions/<session-id>.md`

The initial implementation now follows that shape under a local `out/` directory.

The Markdown export is intentionally more structured than the raw input. It separates conversation content into readable sections instead of mirroring every low-level event line one by one.

The hidden state file exists only to track derived export fingerprints and output paths. It is local mirror bookkeeping, not Codex source state.

## Direction

The main flow should be:

```text
~/.codex/sessions -> parser/extractor -> normalized mirror -> optional transport layer
```

Current command:

```text
scripts/codex-session-mirror
```

Current CLI modes:

```text
scripts/codex-session-mirror
scripts/codex-session-mirror --redact
scripts/codex-session-mirror --out-dir ./out-custom
scripts/codex-session-mirror --no-context
scripts/codex-session-mirror --no-tools
scripts/codex-session-mirror --no-events
scripts/codex-session-mirror --conversation-only
```

Transport is secondary. The mirror should make it possible to use tools like Syncthing or `rsync` safely later, without making them part of the core design.

The exporter remains read-only with respect to Codex source state. Redaction, when enabled, is applied only to the derived mirror files.

Export profile flags affect only the derived Markdown view. They do not change the source session logs and do not introduce any write-back path into Codex state.

Incremental export is now part of the core local flow. Repeated runs may reuse unchanged per-session artifacts, but the source of truth remains the raw session files under `~/.codex/sessions`.

## v1 and v2

The current Bash implementation should now be treated as the frozen v1 baseline.

Planned v2 direction:

- preserve the product architecture
- freeze the mirror contract first
- move the implementation core to Python
- use Python 3.13 as the development baseline and support Python 3.13+
- keep `scripts/` stable until Python reaches parity

See:

- [mirror-contract.md](mirror-contract.md)
- [../history/v2-python-migration.md](../history/v2-python-migration.md)

## Non-Goals

- no write-back to `~/.codex/sessions`
- no raw sync of all `~/.codex`
- no credential transport
- no assumption that internal Codex files are a stable official API
