# Dispatch Artifact

- `dispatch_id`: `MCP-DSP-004`
- `date_utc`: `2026-03-18T19:16:48Z`
- `project`: `codex-portable-context`
- `architect_ref`: `docs/mcp-bridge-v1.md`
- `coordinator_ref`: `workflow/workflow_current.md`
- `worker_id`: `W1`
- `slice_id`: `MCP-CONTROL-002`
- `priority`: `HIGH`

## Objective

- implement the smallest local task-state scaffold for bounded Codex CLI control without yet spawning Codex work

## Scope

- in scope:
  - `src/codex_portable_context/mcp/`
  - `tests/`
- out of scope:
  - any actual Codex CLI execution
  - any daemon, network listener, or remote control surface
  - any claim of Codex App or VS Code extension thread support
  - any task state under `out/`
  - any raw provider-state mutation

## Inputs To Read

- `docs/mcp-bridge-v1.md`
- `docs/openclaw-first-work-plan.md`
- `workflow/outputs/MCP-CONTROL-001_W2.md`
- `workflow/review/MCP-CONTROL-001.md`

## Acceptance Criteria

- the repo has a bounded local task-state data model for control requests
- the first task-state path is clearly separate from `out/`
- tests cover status lifecycle shape and retention metadata without launching Codex
- no execution hook or subprocess launch exists yet

## Verification

- command:
  - repo-local tests for the new task-state scaffold only
  - expected result:
    - the control scaffold validates without changing read-only bridge behavior

## Deliverable

- local task-state scaffold only
- tests
- repo-native worker, validation, and review artifacts for `MCP-CONTROL-002`

## Stop Condition

- stop once the task-state scaffold exists and no execution path is overclaimed

## Validation Note

- `workflow/validation/MCP-CONTROL-002.md`
