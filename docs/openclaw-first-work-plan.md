# OpenClaw First Work Plan

## Purpose

Define the first bounded OpenClaw work queue for the MCP bridge direction.

This plan assumes:

- `codex-portable-context` remains read-only with respect to raw Codex state
- the first bridge target is Codex CLI
- OpenClaw work should be small, reviewable, and reversible

## Ground Rules For OpenClaw

- work in an isolated branch or worktree
- do not change current mirror behavior without explicit justification
- do not add any network-facing default behavior
- do not introduce background services as the default usage path
- prefer docs, contracts, and thin scaffolding before broad implementation
- preserve Windows and Linux portability
- prefer a coordinator-plus-workers split over one agent doing everything
- keep code validation explicit when the pilot host runtime differs from the repo baseline

## Session 01

### Title

Bridge feasibility review

### Objective

Inspect the current Python CLI, artifact readers, and extension-facing contracts, then produce a short implementation-gap report for the MCP bridge.

### Inputs To Read

- `README.md`
- `conventions.md`
- `decision_log.md`
- `docs/architecture.md`
- `docs/mirror-contract.md`
- `docs/extension-invocation-contract.md`
- `docs/list-json-contract.md`
- `docs/mcp-bridge-v1.md`

### Deliverable

Create:

- `docs/openclaw-session-01-bridge-gap-report.md`

### Stop Condition

Stop after the report exists and clearly identifies:

- reusable existing CLI pieces
- missing bridge-facing abstractions
- state-management questions
- the smallest safe implementation slice

## Session 02

### Title

Read-only bridge contract refinement

### Objective

Refine the first read-only tool surface into an implementation-ready internal contract.

### Deliverable

Create or update:

- `docs/openclaw-session-02-read-tools-contract.md`

Minimum sections:

- tool names
- inputs
- outputs
- error cases
- artifact source paths
- redaction expectations

### Stop Condition

Stop after the read-only bridge contract is implementation-ready and does not require live provider-state mutation.

## Session 03

### Title

Scaffold local MCP bridge entrypoint

### Objective

Add a minimal no-surprise Python scaffold for the MCP bridge without changing current mirror behavior.

### Preferred Touch Surface

- `src/codex_portable_context/mcp/`
- `src/codex_portable_context/cli/`
- `tests/`

### Deliverable

Create:

- MCP package skeleton
- minimal entrypoint module
- tests for basic import and no-op startup behavior

### Stop Condition

Stop once the scaffold exists, tests are added, and no read or control tool behavior is overclaimed.

## Session 04

### Title

Implement read-only session listing and handoff retrieval

### Objective

Implement the safest useful subset of the bridge using existing derived artifacts.

### Deliverable

Implement only:

- session listing
- latest session summary lookup
- handoff lookup

### Stop Condition

Stop once these tools work locally against derived artifacts and the validation path passes.

## Session 05

### Title

Codex CLI bounded-control spike

### Objective

Design and, if justified, implement the smallest bounded control path for Codex CLI task enqueue and status retrieval.

The first safe step inside Session 05 is docs-only:

- define the bounded control request and response shape
- define task-state location and retention posture
- keep the control path local-only and Codex-CLI-only

Only after that closes cleanly should a code spike begin.

### Constraint

Do not claim support for Codex App threads or VS Code extension threads.

### Deliverable

One of:

- a conservative implementation spike with tests
- or a stop report explaining why the current surface is still too unstable

The first docs-only checkpoint should leave these decisions explicit:

- direct Codex CLI invocation vs ACP wrapping
- allowed task-state root
- terminal-state retention posture
- bounded result surface

### Stop Condition

Stop once the repo has either:

- a proven bounded control spike
- or a documented no-go with concrete blocking evidence

## Validation Standard

No phase should be considered complete unless:

- docs match the actual code
- existing mirror behavior still passes validation
- the change is clearly optional and additive
- no raw provider-state write-back was introduced
