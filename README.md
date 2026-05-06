# codex-portable-context

`codex-portable-context` turns local Codex session data into a derived, read-only mirror that is easier to browse, move, and review across devices. It is built for safe context portability, not for syncing live `~/.codex` state or writing anything back into Codex.

Current provider status:

- `codex`: primary and validated provider path
- `claude-code`: conservative internal adapter path under fixture-backed development
- `antigravity`: policy-gated, manual-export compatibility only unless an official export/API path is confirmed

Provider guardrails are documented in [docs/provider-policy-guardrails.md](docs/provider-policy-guardrails.md).

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
For very long sessions, the reader keeps the browser responsive by showing a
lightweight transcript preview with links to the full Markdown artifact.
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

Linux-to-Linux handoff workflow:

```bash
.venv/bin/codex-session-mirror --out-dir ./out
.venv/bin/codex-session-handoff --out-dir ./out --latest
rsync -a ./out/ user@other-linux-box:~/codex-portable-context/inbox/out/
```

Expected Linux-to-Windows handoff workflow:

```bash
.venv/bin/codex-session-mirror --out-dir ./out
.venv/bin/codex-session-handoff --out-dir ./out --latest
rsync -a ./out/ /run/media/$USER/TRANSFER/codex-portable-context/out/
```

Then open `index.html` or the generated handoff bundle on the Windows machine. See [docs/linux-to-windows-handoff.md](docs/linux-to-windows-handoff.md).

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
  Useful flags: `--latest`, `--print`, `--restart-prompt`, `--out-dir`
- `codex-session-handoff-audit`
  Useful flags: `--limit`, `--json`, `--no-generate`, `--write-e2e-manifest`, `--out-dir`

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
codex-session-handoff 019cef3a --restart-prompt
codex-session-handoff-audit --limit 20
codex-session-handoff-audit 019cef3a --json
codex-session-handoff-audit --write-e2e-manifest ./out/restart-prompt-e2e.json 019cef3a
```

The handoff audit reports memory quality, restart-prompt compliance, and the
provider-neutral `source_availability` contract used by continuity handoffs.

Both `codex-session-open --help` and `codex-session-latest --help` now include short built-in examples so the common open/print flows are easier to discover from the terminal.

`codex-session-mirror --help`, `codex-session-list --help`, and `codex-session-handoff-audit --help` now follow the same pattern, so the helper commands present examples in a consistent style.

## Python-Primary Status

Python is the active implementation path for v2.

That means:

- the shared implementation lives under `src/codex_portable_context/`
- installed console scripts are the main user-facing path
- direct `python -m ...` invocation is fully supported
- the Bash commands under `scripts/` are temporary compatibility wrappers
- the last full Bash implementation is preserved historically via the `bash-v1-baseline` tag

The product thesis did not change. The tool still builds a derived, read-only mirror and keeps raw Codex state untouched.

## VS Code Integration Direction

VS Code integration is planned as a thin UX layer on top of the Python CLI, not as a second product implementation.

That means:

- Python remains the source of truth for mirror, reader, handoff, and artifact logic
- the future extension should only orchestrate the existing CLI and open generated artifacts
- the project remains fully usable outside VS Code

See [docs/vscode-extension-strategy.md](docs/vscode-extension-strategy.md).

For machine-readable session selection, see the small integration contract for [`codex-session-list --json`](docs/list-json-contract.md). For the thin VS Code frontend surface, see the extension-facing CLI contract in [`docs/extension-invocation-contract.md`](docs/extension-invocation-contract.md).

An initial thin extension skeleton also lives under [`extensions/vscode-codex-portable-context/`](extensions/vscode-codex-portable-context/README.md). It is intentionally a frontend over the Python CLI, not a second implementation.
For the first practical validation pass, see [`docs/vscode-extension-manual-validation.md`](docs/vscode-extension-manual-validation.md).
For local `.vsix` packaging and install, see [`docs/vscode-extension-local-install.md`](docs/vscode-extension-local-install.md).

The planned multi-provider direction is: Codex first, provider abstraction next, Claude Code next, Antigravity next, and only later experimental continuity on top of normalized artifacts. See [docs/multi-provider-strategy.md](docs/multi-provider-strategy.md).

The first internal step of that direction is now in place: Codex is being treated as the first provider adapter behind the Python core, without changing the current CLI UX.

Claude Code now also has a conservative internal adapter path behind the same core, but it remains intentionally fixture-backed and does not yet imply release-ready Claude Code support. See [docs/claude-code-adapter-brief.md](docs/claude-code-adapter-brief.md).

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

For the native Windows setup checklist and the first concrete validation record, see [docs/windows-native-validation.md](docs/windows-native-validation.md).

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
- native Windows setup is documented and an initial native validation record now exists

What is not being claimed yet:

- this repo is not claiming completed Windows-native coverage across all workflows
- the Bash wrappers are not the cross-platform path

For the concrete Windows-native setup checklist and validation record, see [docs/windows-native-validation.md](docs/windows-native-validation.md).

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

The generated browser reader uses the same summary fields and the optional `reader_relpath` field to build a self-contained static UI. After a handoff is generated, the session reader is refreshed with a copy button for the restart prompt.

## Handoff Bundles

`codex-session-handoff` generates a small extractive bundle under `out/handoffs/`:

- `<session-id>.md`
- `<session-id>.json`

The handoff bundle is designed for continuity, not raw session import. It uses the derived mirror as the base and, when the local source session is still available, adds a recent conversation window and recent tool activity without using an API or an LLM.

The handoff now also adds a compact top layer for faster re-entry:

- `Current State`
- expanded `Artifacts`
- `Recent Actions (normalized)`
- `Open Loops / Risks`
- raw audit-trail sections kept lower in the document

The handoff now includes the first continuity bridge layer: a fresh-session re-entry brief with resolved state, durable decisions, changed artifacts, re-entry posture, and a copy-ready restart prompt. See [docs/continuity-bridge-roadmap.md](docs/continuity-bridge-roadmap.md) for the remaining roadmap.

Restart prompts include a continuity freshness guard. If a selected session is
older than another exported session in the same working directory, or the repo
`HEAD` commit is newer than the exported conversation context, the prompt marks
the handoff as potentially stale and tells the next agent to review the latest
same-repo context before implementing.

Handoffs also include a conservative `roadmap_evidence` layer. It discovers and
cites repo-owned roadmap/status docs when they appear useful, but the current
slice does not use them to rewrite the continuation brief or next action.

If a source session lacks a usable cwd, handoff generation can infer the repo
root from dominant absolute artifact paths in the transcript and then report the
branch, HEAD, repo state, and repo-relative inspection targets. Inferred roots
are marked as `repo_root_source=inferred_from_artifact_paths`.

Use `codex-session-handoff 019cef3a --restart-prompt` to print only the generated fresh-session prompt.

Use `codex-session-handoff 019cef3a --before-last-user --restart-prompt`
to print a historical restart prompt from the source session state immediately
before the latest user message. Use `codex-session-handoff 019cef3a --list-turns`
to inspect user-message indexes, then
`codex-session-handoff 019cef3a --before-user 7 --restart-prompt` to cut
before a specific user message. Use `--as-of 2026-05-04T14:52:55Z` when you need
an explicit timestamp boundary. Historical handoffs are written with a snapshot
suffix, so they do not overwrite the canonical handoff for the full session.

Use `codex-session-handoff-audit --limit 20` to sample recent handoffs and check whether `Decisions / Invariants` is producing useful memory or falling back to `no_memory` / `low_confidence`.

For older mirror outputs, path resolution can fall back to:

- `metadata/<session-id>.json`
- `sessions/<session-id>.md`

## Docs

- [docs/architecture.md](docs/architecture.md)
- [docs/continuity-bridge-roadmap.md](docs/continuity-bridge-roadmap.md)
- [docs/handoff.md](docs/handoff.md)
- [docs/linux-to-linux-handoff.md](docs/linux-to-linux-handoff.md)
- [docs/linux-to-windows-handoff.md](docs/linux-to-windows-handoff.md)
- [docs/mirror-contract.md](docs/mirror-contract.md)
- [docs/phase7-parity.md](docs/phase7-parity.md)
- [docs/python-v2-conventions.md](docs/python-v2-conventions.md)
- [docs/security.md](docs/security.md)
- [docs/mvp.md](docs/mvp.md)
- [docs/transport.md](docs/transport.md)
- [docs/v2-python-migration.md](docs/v2-python-migration.md)
- [docs/windows-native-validation.md](docs/windows-native-validation.md)
