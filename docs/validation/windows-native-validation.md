# Windows Native Validation

## Purpose

This document defines the practical Windows-native setup and validation plan for `codex-portable-context`.

It is intentionally concrete:

- do not treat Linux-only testing as proof of Windows-native readiness
- do validate the Python implementation directly on Windows
- do use the Python console entrypoints, not the Bash wrappers

## Current Status

Already covered in the repo today:

- Python is the primary implementation path
- Windows-style path redaction is covered by tests
- opener logic has an explicit Windows path via `os.startfile()`
- derived mirror generation, listing, opening, latest-session, and handoff flows exist in Python

Not yet claimed in general:

- full Windows-native coverage across all workflows and environments
- PowerShell ergonomics beyond the commands documented below
- packaged distribution beyond editable install

## Recommended Windows Setup

Use PowerShell and create an explicit project environment.

```powershell
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -e '.[dev]'
```

If Python 3.13 is not the system default but is available through the `py` launcher, keep using `py -3.13`.

If the machine has a newer Python such as 3.14 and 3.13 is not available, that is not automatically a blocker as long as the code remains compatible and the environment is explicit.

## Recommended Windows Invocation

Preferred command path after installation:

```powershell
.venv\Scripts\codex-session-mirror.exe --help
.venv\Scripts\codex-session-list.exe --help
.venv\Scripts\codex-session-open.exe --help
.venv\Scripts\codex-session-latest.exe --help
```

Fallback module form:

```powershell
.venv\Scripts\python -m codex_portable_context.cli.mirror --help
.venv\Scripts\python -m codex_portable_context.cli.list --help
.venv\Scripts\python -m codex_portable_context.cli.open --help
.venv\Scripts\python -m codex_portable_context.cli.latest --help
```

Do not use the Bash compatibility wrappers as the Windows-native path.

## Validation Checklist

### Environment

- confirm the editable install succeeds
- confirm the console entrypoints are created in `.venv\Scripts\`
- confirm `python -m codex_portable_context.cli.mirror --help` works

### Mirror Export

Run:

```powershell
.venv\Scripts\codex-session-mirror.exe
.venv\Scripts\codex-session-mirror.exe --redact --out-dir .\out-redacted
```

Check:

- `out\README.md` is generated
- `out\sessions-index.jsonl` is generated
- `out\metadata\` and `out\sessions\` contain per-session artifacts
- repeated runs reuse unchanged sessions instead of regenerating everything

### List / Open / Latest

Run:

```powershell
.venv\Scripts\codex-session-list.exe --latest --summary --details
.venv\Scripts\codex-session-open.exe --latest --print
.venv\Scripts\codex-session-open.exe --landing --print
.venv\Scripts\codex-session-latest.exe --metadata --print
```

Check:

- latest selection matches the newest exported session
- `--print` returns valid Windows paths
- `--metadata` and transcript targeting resolve the correct files
- ambiguous id prefixes fail clearly

### Opener Behavior

Run:

```powershell
.venv\Scripts\codex-session-open.exe --latest
.venv\Scripts\codex-session-open.exe --landing
```

Check:

- the default Windows opener launches successfully
- `--print` remains the safe non-opening fallback when direct opening is undesirable

### Redaction

Use Windows-like content when possible, such as:

- `C:\Users\name\project`
- `C:\Users\name\AppData\Local\...`
- `\\server\share\project` if available

Check:

- home-directory paths are redacted conservatively
- obvious secrets still become `<redacted-secret>`
- redaction affects only derived output, not the source logs
- `redaction_report` is present in metadata and index entries

### Line Endings and Filesystem Assumptions

Check:

- CRLF line endings do not break parsing or rendering
- exported Markdown and JSON remain readable after round trips on Windows
- path joins and output locations do not assume Unix separators

## Recommended Manual Validation Commands

After setup:

```powershell
.venv\Scripts\python -m ruff check src tests
.venv\Scripts\python -m mypy src
.venv\Scripts\python -m pytest
```

Then run the CLI checks above against real local Codex data.

## Expected Outcome

Windows-native validation should end with:

- editable install working
- console entrypoints working
- mirror generation working
- helper CLIs working
- opener behavior confirmed
- Windows-style redaction behavior confirmed on real data

If any of those fail, fix the Python implementation directly. Do not add Windows-specific Bash workarounds.

## Native Windows Validation Record

Validation date:

- 2026-03-16

Validated host:

- OS reported by PowerShell: `Microsoft Windows NT 10.0.26200.0`
- Shell: `PowerShell 5.1.26100.7920`
- Project interpreter: `Python 3.13.5` via `py -3.13`
- Host default `python`: `Python 3.10.11`

Installation path actually executed:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

What was validated on that machine:

- installed entrypoint help for `codex-session-mirror`, `codex-session-list`, `codex-session-open`, and `codex-session-latest`
- module help for `python -m codex_portable_context.cli.{mirror,list,open,latest}`
- fixture-backed mirror export, list, `open --print`, `open --metadata --print`, `latest --print`, and `latest --metadata --print`
- real local-source mirror export from `%USERPROFILE%\.codex\sessions`
- real local-source `list --latest --summary --details`
- real local-source `open --latest --print`
- real local-source `latest --metadata --print`
- CRLF fixture parsing and output generation
- default Codex home resolution to `%USERPROFILE%\.codex`

Windows-specific issues found in that pass:

- editable install was missing native `codex-session-*` console entrypoints before `project.scripts` was added
- Windows home paths inside JSON metadata were only partially redacted before JSON-escaped backslash handling was added
- Bash compatibility wrappers were not treated as the native Windows execution path

Fixes kept from that pass because they remain compatible with the current repo:

- `project.scripts` entrypoints for the Python CLIs
- JSON-escaped Windows home path redaction in the Python redactor
- installed-entrypoint coverage in the test suite

What remains unverified from that pass:

- actual GUI opener behavior without `--print`
- Bash wrapper support as a native Windows path
- wider performance coverage beyond the local source used during validation
