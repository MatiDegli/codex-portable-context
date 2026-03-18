# Dispatch Artifact

- `dispatch_id`: `MCP-DSP-005`
- `date_utc`: `2026-03-18T19:21:03Z`
- `project`: `codex-portable-context`
- `architect_ref`: `docs/mcp-bridge-v1.md`
- `coordinator_ref`: `workflow/workflow_current.md`
- `worker_id`: `W1`
- `slice_id`: `MCP-CONTROL-003`
- `priority`: `HIGH`

## Objective

- expose bounded enqueue, status, and result helpers over the local task-state scaffold without launching Codex yet

## Scope

- in scope:
  - `src/codex_portable_context/mcp/`
  - `tests/`
- out of scope:
  - any subprocess launch or actual Codex CLI execution
  - any daemon, network listener, or remote control surface
  - any app-thread or extension-thread claim
  - any task state under `out/`
  - any raw provider-state mutation

## Inputs To Read

- `docs/mcp-bridge-v1.md`
- `workflow/outputs/MCP-CONTROL-002_W1.md`
- `workflow/review/MCP-CONTROL-002.md`

## Acceptance Criteria

- the repo exposes bounded helper functions for:
  - queueing a task record
  - loading task status by id
  - returning bounded result metadata from the local task record
- tests cover the helper behavior without launching Codex
- the slice does not widen into actual execution hooks

## Verification

- command:
  - repo-local tests for the new control helper surface only
  - expected result:
    - the helper layer validates without changing read-only bridge behavior

## Deliverable

- bounded control helper surface only
- tests
- repo-native worker, validation, and review artifacts for `MCP-CONTROL-003`

## Stop Condition

- stop once the helper surface exists and actual execution is still out of scope

## Validation Note

- `workflow/validation/MCP-CONTROL-003.md`
