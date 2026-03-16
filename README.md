# codex-portable-context

`codex-portable-context` turns local Codex session data into a derived, read-only mirror that is easier to browse, move, and review across devices. It is built for safe context portability, not for syncing live `~/.codex` state or writing anything back into Codex.

## What It Does

- reads local session logs from `~/.codex/sessions`
- builds a derived mirror under `out/` or `out-redacted/`
- keeps the source state in `~/.codex` untouched
- provides small helper commands for listing and opening exported sessions

## What It Does Not Do

- it does not sync raw `~/.codex`
- it does not copy `auth.json` or runtime state
- it does not resume sessions
- it does not add a daemon, backend, or network dependency

## Quick Start

Create the default mirror:

```bash
./scripts/codex-session-mirror
```

Create a redacted mirror:

```bash
./scripts/codex-session-mirror --redact
```

List recent exported sessions:

```bash
./scripts/codex-session-list --latest --summary
```

Print the mirror landing page path:

```bash
./scripts/codex-session-open --landing --print
```

Open the latest exported session:

```bash
./scripts/codex-session-open --latest
```

If you are browsing a copied or synced mirror directly, start with `out/README.md`.

## Mirror Output

By default the exporter writes:

```text
out/
├── .codex-session-mirror-state.jsonl
├── README.md
├── sessions-index.jsonl
├── metadata/
│   └── <session-id>.json
└── sessions/
    └── <session-id>.md
```

Use `out/README.md` as the main entry point when browsing the mirror on another device. It is generated from the derived index, includes a small "Start Here" section for the newest session, links to each transcript and metadata file, and stays self-contained after copy or sync.

Repeated runs reuse unchanged derived artifacts when possible. The hidden state file is local bookkeeping for the mirror output only.

## Common Commands

Default export:

```bash
./scripts/codex-session-mirror
```

Redacted export:

```bash
./scripts/codex-session-mirror --redact
```

Conversation-focused export:

```bash
./scripts/codex-session-mirror --conversation-only
```

Trim selected sections:

```bash
./scripts/codex-session-mirror --no-context --no-events
./scripts/codex-session-mirror --no-tools
```

Use a custom output directory:

```bash
./scripts/codex-session-mirror --out-dir ./out-custom
```

## Helper Commands

These commands operate only on the derived mirror, never on raw `~/.codex`.

- `./scripts/codex-session-list`
  Useful flags: `--limit`, `--latest`, `--title`, `--id`, `--summary`, `--details`, `--redaction`, `--json`
- `./scripts/codex-session-open <session-id-or-prefix>`
  Useful flags: `--metadata`, `--print`, `--out-dir`, `--landing`, `--latest`
- `./scripts/codex-session-latest`
  Useful flags: `--metadata`, `--print`, `--out-dir`

Examples:

```bash
./scripts/codex-session-list --latest
./scripts/codex-session-list --latest --summary --details
./scripts/codex-session-list --title galaxy --limit 5
./scripts/codex-session-list --out-dir ./out-redacted --latest --redaction
./scripts/codex-session-open 019cef3a --print
./scripts/codex-session-open --metadata 019cef3a --print
./scripts/codex-session-latest --print
./scripts/codex-session-latest --metadata --print
```

Both `codex-session-open --help` and `codex-session-latest --help` now include short built-in examples so the common open/print flows are easier to discover from the terminal.

`codex-session-mirror --help` and `codex-session-list --help` now follow the same pattern, so all four main helper commands present examples in a consistent style.

## v2 Direction

v1 is now the frozen Bash baseline.

The next planned architecture step is a Python-based v2 so the project can support:

- Linux native
- Windows native
- real cross-OS portability
- the same conceptual UX across platforms

This is intended as an implementation shift, not a product-thesis shift. The derived mirror remains the core output.

## Export Quality

The transcript export is optimized for useful reading. It separates:

- session context
- user messages
- assistant messages
- tool calls
- tool outputs
- notable lifecycle events

Routine low-value records such as `token_count` and `turn_context` are omitted from Markdown to keep exports readable. This filtering is conservative and documented; the source session files remain unchanged.

Each session also gets a small mechanical summary in metadata and in `sessions-index.jsonl`, and each transcript begins with a compact session snapshot so recent work is easier to scan quickly.

`codex-session-list --summary --details` uses those exported summary fields to show a compact preview, activity line, and environment line directly in the terminal.

## Redaction

Redaction is optional and applies only to derived output.

When enabled, the exporter uses conservative placeholders such as:

- `<redacted-user>`
- `<redacted-home>`
- `<redacted-host>`
- `<redacted-secret>`

Per-session metadata and index entries include a `redaction_report` object so you can see whether redaction ran and how many best-effort replacements were made.

Redaction is helpful for safer transport, but it is not a guaranteed DLP or privacy system. Review the result before sharing or moving it to a less-trusted device.

## Transport

Transport is optional and intentionally outside the core tool.

Recommended transport target:

- the derived mirror only, such as `out/` or `out-redacted/`

Do not treat these as transport targets:

- `~/.codex/auth.json`
- `~/.codex/config.toml`
- `~/.codex/state_*.sqlite`
- `~/.codex/logs_*.sqlite`
- `~/.codex/tmp/`
- `~/.codex/shell_snapshots/`

For transport recipes, see [docs/transport.md](docs/transport.md). The documented approaches are:

- Syncthing, with a bias toward one writer and a read-oriented copy
- one-way `rsync`, for explicit directional control

## Index Contract

The helper commands read only the exported mirror index:

- `out/sessions-index.jsonl`

They currently rely on these fields:

- `session_id`
- `title`
- `updated_at`
- `session_timestamp`
- `metadata_relpath`
- `markdown_relpath`
- `summary.preview`
- `summary.activity`
- `summary.environment`
- `summary.detail_line`
- `summary.one_line`
- `redaction_report`

The generated landing page also uses the exported summary fields to show a short preview, activity line, and environment line for each session.

For older mirror outputs, path resolution can fall back to:

- `metadata/<session-id>.json`
- `sessions/<session-id>.md`

## Docs

- [docs/architecture.md](docs/architecture.md)
- [docs/mirror-contract.md](docs/mirror-contract.md)
- [docs/python-v2-conventions.md](docs/python-v2-conventions.md)
- [docs/security.md](docs/security.md)
- [docs/mvp.md](docs/mvp.md)
- [docs/transport.md](docs/transport.md)
- [docs/v2-python-migration.md](docs/v2-python-migration.md)
