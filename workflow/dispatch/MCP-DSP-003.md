# Dispatch Artifact

- `dispatch_id`: `MCP-DSP-003`
- `date_utc`: `2026-03-18T19:10:01Z`
- `project`: `codex-portable-context`
- `architect_ref`: `docs/openclaw-first-work-plan.md`
- `coordinator_ref`: `workflow/workflow_current.md`
- `worker_id`: `W2`
- `slice_id`: `MCP-CONTROL-001`
- `priority`: `HIGH`

## Objective

- define the smallest bounded Codex CLI control contract and task-state posture without implementing live control code yet

## Scope

- in scope:
  - `docs/mcp-bridge-v1.md`
  - `docs/openclaw-first-work-plan.md`
  - one repo-native worker record under `workflow/outputs/`
- out of scope:
  - any code change under `src/`
  - any daemon, network listener, or remote control surface
  - any claim of Codex App or VS Code extension thread support
  - any mutation of raw provider state

## Inputs To Read

- `docs/mcp-bridge-v1.md`
- `docs/openclaw-first-work-plan.md`
- `workflow/outputs/MCP-READ-001_W1.md`
- `workflow/outputs/MCP-READ-002_W1.md`
- `workflow/review/MCP-READ-002.md`

## Acceptance Criteria

- the docs define a bounded control request/response shape for Codex CLI only
- the docs name the allowed task-state location and retention posture
- the docs state explicit non-goals for app-thread, extension-thread, and live-session mutation
- the slice stays docs-only

## Verification

- command:
  - review-based consistency check against current MCP docs and workflow artifacts
  - expected result:
    - docs stay aligned with the read-only bridge posture and do not overclaim implementation

## Deliverable

- one bounded docs update for the first control-surface design
- repo-native worker, validation, and review artifacts for `MCP-CONTROL-001`

## Stop Condition

- stop once the bounded control design is explicit enough to decide whether a later code spike is justified

## Validation Note

- `workflow/validation/MCP-CONTROL-001.md`
