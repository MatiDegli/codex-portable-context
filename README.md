# codex-portable-context

[![CI](https://github.com/MatiDegli/codex-portable-context/actions/workflows/ci.yml/badge.svg)](https://github.com/MatiDegli/codex-portable-context/actions/workflows/ci.yml)

I work with AI coding agents on more than one machine, and a session's context stays
on the computer where it happened. This tool turns local Codex session logs into a
read-only mirror you can browse, copy to another device, and use to restart the work
in a fresh session.

It never writes back into `~/.codex`, never copies credentials, and has no network
calls or runtime dependencies.

## What it does

- **Mirror.** Reads `~/.codex/sessions/**/*.jsonl` and exports each session as
  readable Markdown, JSON metadata and a static HTML reader with filtering. Repeated
  runs reuse unchanged output.
- **Handoff.** Builds a short re-entry brief for a session: current state, decisions,
  changed files, open loops and a copy-ready restart prompt. It is extractive: no LLM
  or API is involved.
- **Redaction.** Optionally replaces user names, home paths, hosts and secrets in the
  derived output. It is best-effort, not a privacy guarantee.
- **VS Code extension.** A thin frontend over the CLI in
  [`extensions/`](extensions/vscode-codex-portable-context).

Codex is the supported source. A Claude Code adapter exists but is still experimental.

## Quick start

Requires Python 3.13+.

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"

.venv/bin/codex-session-mirror                 # export to ./out
.venv/bin/codex-session-list --latest --summary
.venv/bin/codex-session-handoff --latest --print
```

Open `out/index.html` in a browser, or `out/README.md` as a plain entry point.

| Command | Purpose |
| --- | --- |
| `codex-session-mirror` | Export the mirror (`--redact`, `--conversation-only`, `--out-dir`) |
| `codex-session-list` | List exported sessions (`--latest`, `--title`, `--json`) |
| `codex-session-open` / `codex-session-latest` | Print or open a session, reader or handoff |
| `codex-session-handoff` | Generate a handoff bundle under `out/handoffs/` |
| `codex-session-handoff-audit` | Check handoff quality across sessions |
| `codex-session-context-pack` | Combine several handoffs into one context pack |

Every command has `--help` with examples.

## Moving the mirror

Copy only the derived output (`out/` or `out-redacted/`), for example with one-way
`rsync` or Syncthing. Never sync `~/.codex` itself. See [docs/transport.md](docs/transport.md).

## Development

```bash
.venv/bin/ruff check .
.venv/bin/mypy
.venv/bin/pytest
```

## Docs

- [Architecture](docs/architecture.md)
- [Mirror output contract](docs/mirror-contract.md)
- [Handoff bundles](docs/handoff.md)
- [Security](docs/security.md)
- [Provider policy](docs/provider-policy-guardrails.md)

MIT License.
