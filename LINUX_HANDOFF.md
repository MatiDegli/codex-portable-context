# Linux Handoff

This file is the root handoff for opening the next chat in a native Linux clone of this repo.

Use it as the first file to read.

## PM Start Here

The PM should continue from this branch:

- `codex/linux-migration-checkpoint`

Recommended Linux start sequence:

1. clone the repo on Linux
2. checkout `codex/linux-migration-checkpoint`
3. open a new repo-local chat from that Linux clone
4. have that chat read this file first
5. then have that chat read the files listed in `Read These First`
6. bootstrap the native Linux environment
7. run the Linux validation block before planning any new implementation slice

If Linux validation passes, continue from the current checkpoint rather than reopening older MCP slices.

## Current State

The repo is now at a migration-readiness checkpoint.

What already exists:

- read-only MCP bridge helpers over derived artifacts
- local task-state scaffold for bounded control work
- bounded enqueue/status/result helpers that still do not launch Codex
- repo-native workflow artifacts under `workflow/`

What does not exist yet:

- a real Codex CLI launch hook
- any daemon or remote service behavior
- any Codex App or VS Code thread control path

## Read These First

1. `workflow/workflow_current.md`
2. `workflow/outputs/MCP-CONTROL-003_W1.md`
3. `workflow/review/MCP-CONTROL-003.md`
4. `docs/mcp-bridge-v1.md`
5. `docs/openclaw-first-work-plan.md`
6. `decision_log.md`
7. `conventions.md`

## Linux Bootstrap

From the repo root on Linux:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Linux Validation

Run these from the repo root:

```bash
python -m pytest tests/test_mcp_bridge.py -q
python -m pytest tests/test_mcp_task_state.py -q
python -m pytest tests/test_mcp_control.py -q
python -m ruff check src/codex_portable_context/mcp src/codex_portable_context/cli/mcp.py tests/test_mcp_bridge.py tests/test_mcp_task_state.py tests/test_mcp_control.py
python -m codex_portable_context.cli.mcp --help
codex-session-mcp --help
```

Expected minimum:

- the three targeted test files pass
- Ruff passes on the MCP surface
- both CLI help commands work

## Recommended First Linux Task

Do not open the real Codex launch hook immediately.

First:

1. clone the repo cleanly on Linux
2. checkout `codex/linux-migration-checkpoint`
3. recreate the Python environment natively
4. rerun the MCP bridge, task-state, and control-helper validations
5. confirm the workflow still looks the same in Linux

Only after that decide whether to start the first real Codex CLI launch hook.

## Next Likely Slice

If Linux validation is clean, the next likely slice is:

- first real Codex CLI launch hook

Constraints for that slice:

- local-only
- no daemon default
- no app-thread or extension-thread assumptions
- no raw provider-state mutation
- bounded task record must remain the source of truth

## Role Handoff

The next chat in the Linux clone should continue with this role:

- preserve the current architect -> coordinator -> worker -> reviewer workflow
- treat `workflow/` artifacts as the live source of truth
- avoid reopening already-closed slices unless Linux validation proves drift
- keep the next implementation bounded and auditable
- assume the PM has already selected `codex/linux-migration-checkpoint` as the continuation branch

## Migration Decision

Current recommendation:

- migrate now
- continue implementation from Linux, not from the current WSL2 pilot host
