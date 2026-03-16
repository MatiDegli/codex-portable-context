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
- derived mirror generation, listing, opening, and latest-session flows exist in Python

Not yet claimed from this environment:

- full native Windows validation
- PowerShell-specific ergonomics beyond the documented commands below
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
