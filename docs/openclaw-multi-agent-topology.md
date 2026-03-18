# OpenClaw Multi-Agent Topology

## Purpose

Define the first controlled multi-agent operating model for `codex-portable-context`.

The goal is to let OpenClaw behave as a coordinator for bounded work, not as a single free-roaming coding agent.

## Agent Roles

### `codex-portable-context`

Role:

- coordinator

Responsibilities:

- read architect guidance, the bridge spec, and completed session reports
- decide the next bounded slice
- dispatch only narrow work to the workers
- stop on ambiguity instead of widening scope

Normal touch surface:

- `docs/`
- planning notes in the isolated pilot worktree

### `codex-portable-context-mcp-scaffold`

Role:

- code scaffold worker

Responsibilities:

- implement thin MCP bridge slices only after the coordinator defines the scope
- stay inside the agreed Python touch surface

Allowed touch surface:

- `src/codex_portable_context/mcp/`
- `src/codex_portable_context/cli/`
- `tests/`

### `codex-portable-context-mcp-contracts`

Role:

- docs and contract worker

Responsibilities:

- refine contracts, docs, and implementation notes from coordinator instructions
- avoid code unless explicitly redirected

Allowed touch surface:

- `docs/`

## Operating Rules

- one bounded slice per worker at a time
- coordinator should prefer docs, contracts, and validation planning before wider implementation
- workers should stop once the assigned slice is complete
- no worker should expand into app-thread control, VS Code thread control, or raw session write-back
- no worker should enable network-facing defaults

## Current Pilot Constraint

The repo baseline is Python `3.13+`, while the current WSL2 pilot host is still on Python `3.10`.

Until the WSL runtime is upgraded, validation should use the existing Windows virtual environment from PowerShell:

```powershell
$env:PYTHONPATH='C:\Criticos\Proyectos\_worktrees\codex-portable-context-openclaw\src'
C:\Criticos\Proyectos\codex-portable-context\.venv\Scripts\python.exe -m pytest tests/test_cli_mcp.py tests/test_mcp_scaffold.py -q
```

This is a temporary pilot workaround, not the target Linux-native validation path.

## Cron Policy

- do not schedule recurring code-writing jobs yet
- first recurring jobs, if any, should be coordinator-only status or dispatch runs
- only enable recurring implementation jobs after one full manual coordinator-to-worker cycle validates cleanly
