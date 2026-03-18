# Dispatch Artifact

- `dispatch_id`: `MCP-DSP-002`
- `date_utc`: `2026-03-18T18:57:54Z`
- `project`: `codex-portable-context`
- `architect_ref`: `docs/openclaw-first-work-plan.md`
- `coordinator_ref`: `workflow/workflow_current.md`
- `worker_id`: `W1`
- `slice_id`: `MCP-READ-002`
- `priority`: `HIGH`

## Objective

- close the next bounded read-only gap by adding latest-session summary lookup and artifact lookup over the derived mirror only

## Scope

- in scope:
  - `src/codex_portable_context/mcp/bridge.py`
  - `src/codex_portable_context/cli/mcp.py`
  - `tests/`
- out of scope:
  - any control tool or task registry behavior
  - any network listener, server default, or daemon requirement
  - any mutation of raw provider state
  - any Codex App or VS Code extension thread control claim
  - any change to mirror export semantics

## Inputs To Read

- `docs/mcp-bridge-v1.md`
- `docs/openclaw-first-work-plan.md`
- `workflow/outputs/MCP-READ-001_W1.md`
- `workflow/validation/MCP-READ-001.md`
- `workflow/review/MCP-READ-001.md`

## Acceptance Criteria

- the bridge exposes a latest-session summary lookup that reads only from derived artifacts already owned by the repo
- the bridge exposes artifact lookup for a selected session without reparsing raw provider state
- tests cover happy path plus bounded error cases for missing or ambiguous selectors
- the CLI remains a local inspection surface only
- the slice leaves control-tool work explicitly out of scope

## Verification

- command:
  - `$env:PYTHONPATH='<worktree-or-repo-src-path>'`
  - `C:\Criticos\Proyectos\codex-portable-context\.venv\Scripts\python.exe -m pytest tests/test_mcp_bridge.py -q`
  - expected result:
    - the expanded bounded bridge test set passes

## Deliverable

- bounded read-only support for:
  - latest session summary lookup
  - session artifact lookup
- updated tests
- repo-native worker, validation, and review artifacts for `MCP-READ-002`

## Stop Condition

- stop once the bounded read-only slice is implemented, validated honestly, and still stays above the derived mirror

## Validation Note

- `workflow/validation/MCP-READ-002.md`
