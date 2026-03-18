# Dispatch Artifact

- `dispatch_id`: `MCP-DSP-001`
- `date_utc`: `2026-03-18T18:57:54Z`
- `project`: `codex-portable-context`
- `architect_ref`: `docs/openclaw-first-work-plan.md`
- `coordinator_ref`: `docs/openclaw-multi-agent-topology.md`
- `worker_id`: `W1`
- `slice_id`: `MCP-READ-001`
- `priority`: `HIGH`

## Objective

- implement the first truthful read-only MCP bridge subset using existing derived artifacts only

## Scope

- in scope:
  - `src/codex_portable_context/mcp/bridge.py`
  - `src/codex_portable_context/cli/mcp.py`
  - `tests/test_mcp_bridge.py`
- out of scope:
  - any network listener, daemon, or server mode
  - any mutation of raw provider state
  - any Codex App or VS Code thread support claim
  - any bounded control tools
  - any change to the existing mirror contract

## Inputs To Read

- `docs/mcp-bridge-v1.md`
- `docs/openclaw-first-work-plan.md`
- `conventions.md`

## Acceptance Criteria

- `session_list` reads from the derived mirror and returns bounded payloads with absolute artifact paths
- `session_handoff_get` generates or refreshes one handoff bundle from the derived mirror only
- the CLI remains a local inspection surface and does not imply server behavior
- tests cover the bounded happy paths for the new helper layer

## Verification

- command:
  - `$env:PYTHONPATH='C:\Criticos\Proyectos\_worktrees\codex-portable-context-mcp-scaffold\src'`
  - `C:\Criticos\Proyectos\codex-portable-context\.venv\Scripts\python.exe -m pytest tests/test_mcp_bridge.py -q`
  - expected result:
    - `3 passed`

## Deliverable

- bounded read-only bridge helper and CLI support for:
  - `session_list`
  - `session_handoff_get`
- one repo-native worker record under `workflow/outputs/`
- one validation note under `workflow/validation/`

## Stop Condition

- stop once the bounded read-only slice is implemented, validated honestly, and does not overclaim control or live-thread support

## Validation Note

- `workflow/validation/MCP-READ-001.md`
