# codex-portable-context Conventions

This file is the highest authority for local code, documentation, and workflow rules unless it explicitly delegates otherwise.

## Authority Order

1. `conventions.md`
2. repo-wide bootstrap and operating docs such as `README.md`
3. module- and domain-specific docs under `docs/`
4. reference notes and release drafts

If guidance conflicts, stop and resolve it explicitly.

## Local Non-Negotiables

- Environment:
  Use an explicit project environment. Prefer Python 3.13 when available. Do not rely on the host default Python implicitly.
- Execution:
  Use documented entrypoints from the repo root. Prefer `python -m ...` for Python v2 code and keep Bash v1 scripts unchanged until parity is reached.
- Mirror safety:
  The project remains local-first and read-only with respect to Codex source state. No raw sync of `~/.codex`, no write-back, no credential sync.
- Contract:
  Follow [docs/architecture/mirror-contract.md](/home/matidegli/Projects/codex-sync/docs/architecture/mirror-contract.md) before changing derived mirror output.
- Release:
  Do not treat work as release-ready unless the documented validation path passes.

## Required Rules

- Keep v1 Bash behavior stable while building v2 Python.
- Reuse the shared Python core instead of re-implementing logic independently per CLI.
- Respect `.gitignore` and secret-handling rules.
- Keep generated or local-only artifacts out of git unless they are intentional repo records.

## Stop-The-Line Conditions

- any change that writes back into Codex source state
- any change that silently breaks the frozen mirror contract
- any change that makes Windows support depend on Unix-only tooling again
- any release-ready claim without running the documented validation path
- any commit of real secrets, active env files, or private mirror artifacts

## Canonical Commands

Bootstrap Python v2 environment:

```bash
./scripts/bootstrap-python-v2
```

Bootstrap Python v2 environment on native Windows PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Validate Python v2 baseline:

```bash
./scripts/validate-python-v2
```

Validate Python v2 baseline on native Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m ruff check src tests
.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe -m pytest
```

Current v1 mirror command:

```bash
./scripts/codex-session-mirror
```

## Quality Gates

Commit-ready for Python v2 work:

- `./scripts/validate-python-v2`

Release-ready:

- mirror contract unchanged or explicitly updated with justification
- docs aligned with the actual behavior
- repo clean
- release note or release draft updated when relevant
