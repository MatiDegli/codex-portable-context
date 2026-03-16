# codex-portable-context

`codex-portable-context` turns local Codex session data into a derived, read-only mirror that is easier to browse, move, and review across devices. It is built for safe context portability, not for syncing live `~/.codex` state or writing anything back into Codex.

## What It Does

- reads local session logs from `~/.codex/sessions`
- builds a derived mirror under `out/` or `out-redacted/`
- keeps the source state in `~/.codex` untouched
- provides small helper commands for listing and opening exported sessions
- can generate extractive handoff bundles for starting work on another device without write-back

## What It Does Not Do

- it does not sync raw `~/.codex`
- it does not copy `auth.json` or runtime state
- it does not resume sessions
- it does not add a daemon, backend, or network dependency

## Python-First Quick Start

Recommended path: create an explicit environment, install the package in editable mode, and use the Python entrypoints directly.

Linux:

```bash
./scripts/bootstrap-python-v2
.venv/bin/codex-session-mirror
.venv/bin/codex-session-list --latest --summary
.venv/bin/codex-session-handoff --latest
```

Windows PowerShell:

```powershell
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -e '.[dev]'
.venv\Scripts\codex-session-mirror.exe
.venv\Scripts\codex-session-list.exe --latest --summary
```

Direct module invocation is also supported:

```bash
.venv/bin/python -m codex_portable_context.cli.mirror
```

If you are browsing a copied or synced mirror directly, start with `out/README.md`.
If you want a browser-friendly view, open `out/index.html`.

## Mirror Output

By default the exporter writes:

```text
out/
├── .codex-session-mirror-state.jsonl
├── README.md
├── index.html
├── sessions-index.jsonl
├── metadata/
│   └── <session-id>.json
├── reader/
│   └── <session-id>.html
└── sessions/
    └── <session-id>.md
```

Use `out/README.md` as the main entry point when browsing the mirror on another device. It is generated from the derived index, includes a small "Start Here" section for the newest session, links to each transcript and metadata file, and stays self-contained after copy or sync.

Use `out/index.html` when you want a static browser UI. It is generated from the same derived mirror, adds client-side filtering, and links to a per-session reader page plus the raw Markdown and JSON exports.
Per-session reader pages also include quick jump links for snapshot, metadata, transcript, and raw metadata.
When a handoff bundle exists, the same reader surface also points at the expected `handoffs/` artifacts.

Repeated runs reuse unchanged derived artifacts when possible. The hidden state file is local bookkeeping for the mirror output only.

## Install and Run

The minimal install story is intentionally small:

- local development: editable install in a project `venv`
- local usage: run the installed console scripts from that `venv`
- fallback usage: `python -m codex_portable_context.cli.<command>`
- Bash wrappers: transitional only, not the primary path

Linux setup:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Windows setup:

```powershell
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -e '.[dev]'
```

Installed console entrypoints:

```bash
.venv/bin/codex-session-mirror
.venv/bin/codex-session-list
.venv/bin/codex-session-open
.venv/bin/codex-session-latest
.venv/bin/codex-session-handoff
```

```powershell
.venv\Scripts\codex-session-mirror.exe
.venv\Scripts\codex-session-list.exe
.venv\Scripts\codex-session-open.exe
.venv\Scripts\codex-session-latest.exe
```

Module fallback:

```bash
.venv/bin/python -m codex_portable_context.cli.mirror
.venv/bin/python -m codex_portable_context.cli.list
.venv/bin/python -m codex_portable_context.cli.open
.venv/bin/python -m codex_portable_context.cli.latest
```

Default export:

```bash
.venv/bin/codex-session-mirror
```

Generate a handoff bundle for the latest session:

```bash
.venv/bin/codex-session-handoff --out-dir ./out --latest
```

Open the browser reader:

```bash
python -m webbrowser out/index.html
```

Redacted export:

```bash
.venv/bin/codex-session-mirror --redact
```

Conversation-focused export:

```bash
.venv/bin/codex-session-mirror --conversation-only
```

Trim selected sections:

```bash
.venv/bin/codex-session-mirror --no-context --no-events
.venv/bin/codex-session-mirror --no-tools
```

Use a custom output directory:

```bash
.venv/bin/codex-session-mirror --out-dir ./out-custom
```

## Helper Commands

These commands operate only on the derived mirror, never on raw `~/.codex`.

- `codex-session-list`
  Useful flags: `--limit`, `--latest`, `--title`, `--id`, `--summary`, `--details`, `--redaction`, `--json`
- `codex-session-open <session-id-or-prefix>`
  Useful flags: `--metadata`, `--reader`, `--handoff`, `--print`, `--out-dir`, `--landing`, `--latest`
- `codex-session-latest`
  Useful flags: `--metadata`, `--reader`, `--handoff`, `--print`, `--out-dir`
- `codex-session-handoff`
  Useful flags: `--latest`, `--print`, `--out-dir`

Examples:

```bash
codex-session-list --latest
codex-session-list --latest --summary --details
codex-session-list --title galaxy --limit 5
codex-session-list --out-dir ./out-redacted --latest --redaction
codex-session-open 019cef3a --print
codex-session-open --landing --reader --print
codex-session-open 019cef3a --reader --print
codex-session-open 019cef3a --handoff --print
codex-session-open --metadata 019cef3a --print
codex-session-latest --print
codex-session-latest --reader --print
codex-session-latest --handoff --print
codex-session-latest --metadata --print
codex-session-handoff --latest
codex-session-handoff 019cef3a --print
```

Both `codex-session-open --help` and `codex-session-latest --help` now include short built-in examples so the common open/print flows are easier to discover from the terminal.

`codex-session-mirror --help` and `codex-session-list --help` now follow the same pattern, so all four main helper commands present examples in a consistent style.

## Python-Primary Status

Python is the active implementation path for v2.

That means:

- the shared implementation lives under `src/codex_portable_context/`
- installed console scripts are the main user-facing path
- direct `python -m ...` invocation is fully supported
- the Bash commands under `scripts/` are temporary compatibility wrappers
- the last full Bash implementation is preserved historically via the `bash-v1-baseline` tag

The product thesis did not change. The tool still builds a derived, read-only mirror and keeps raw Codex state untouched.

## Bootstrap and Validation

Canonical bootstrap path:

```bash
./scripts/bootstrap-python-v2
```

Canonical validation path:

```bash
./scripts/validate-python-v2
```

The current Python baseline uses:

- `pytest` for tests
- `ruff` for linting
- `mypy` for static typing

After the editable install, the recommended commands are:

```bash
.venv/bin/codex-session-mirror --help
.venv/bin/codex-session-list --help
.venv/bin/codex-session-open --help
.venv/bin/codex-session-latest --help
```

## Python v2 Baseline

The planned Python v2 work uses this runtime policy:

- baseline development target: Python 3.13
- supported target: Python 3.13+
- host operating systems may have a newer system Python and that is acceptable
- project environments should be created explicitly instead of relying on the host default Python implicitly

Recommended development setup:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
```

After the environment is bootstrapped, the Python mirror exporter can be run with:

```bash
.venv/bin/codex-session-mirror
.venv/bin/codex-session-mirror --redact
.venv/bin/codex-session-mirror --out-dir ./out-python
```

If the host default Python is newer, that is not automatically a problem. The project baseline is about the project environment, not about forcing the operating system itself to use Python 3.13 as its system Python.

## Wrapper Status

The Bash entrypoints:

- `./scripts/codex-session-mirror`
- `./scripts/codex-session-list`
- `./scripts/codex-session-open`
- `./scripts/codex-session-latest`

are now transitional compatibility wrappers over the Python CLIs.

That means:

- existing shell-oriented usage still works through the familiar command names
- direct Python invocation is supported and recommended for v2 workflows
- installed console scripts inside the project `venv` are the main recommended path
- Bash remains in the repo for a short compatibility window, but it is no longer the architectural center
- the last full Bash implementation remains available historically via the `bash-v1-baseline` tag

## Cross-Platform Support Status

Current status:

- Linux is the main day-to-day development and validation environment
- Python v2 is designed for Linux and Windows native usage
- cross-OS path handling and Windows-style path redaction are covered by tests
- native Windows command validation is planned explicitly and documented

What is not being claimed yet:

- this repo is not claiming completed Windows-native validation from this Linux environment
- the Bash wrappers are not the cross-platform path

For the concrete Windows-native setup and validation checklist, see [docs/windows-native-validation.md](docs/windows-native-validation.md).

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

The generated browser reader uses the same summary fields and the optional `reader_relpath` field to build a self-contained static UI.

## Handoff Bundles

`codex-session-handoff` generates a small extractive bundle under `out/handoffs/`:

- `<session-id>.md`
- `<session-id>.json`

The handoff bundle is designed for continuity, not raw session import. It uses the derived mirror as the base and, when the local source session is still available, adds a recent conversation window and recent tool activity without using an API or an LLM.

For older mirror outputs, path resolution can fall back to:

- `metadata/<session-id>.json`
- `sessions/<session-id>.md`

## Docs

- [docs/architecture.md](docs/architecture.md)
- [docs/handoff.md](docs/handoff.md)
- [docs/mirror-contract.md](docs/mirror-contract.md)
- [docs/phase7-parity.md](docs/phase7-parity.md)
- [docs/python-v2-conventions.md](docs/python-v2-conventions.md)
- [docs/security.md](docs/security.md)
- [docs/mvp.md](docs/mvp.md)
- [docs/transport.md](docs/transport.md)
- [docs/v2-python-migration.md](docs/v2-python-migration.md)
- [docs/windows-native-validation.md](docs/windows-native-validation.md)
