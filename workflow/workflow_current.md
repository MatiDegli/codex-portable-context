# Workflow Current

- `updated_utc`: `2026-03-18T19:24:46Z`
- `project`: `codex-portable-context`
- `project_tier`: `Tier 1`
- `current_phase`: `MCP bridge v1 / bounded control helpers closed, live launch hook still deferred`
- `current_priority_stack`:
  1. keep the new read-only MCP surface honest, local-only, and aligned with the derived mirror
  2. decide whether the next slice should add a real Codex CLI launch hook or pause for Linux migration preparation
  3. keep mirror behavior and local-first guardrails unchanged
- `global_blockers`:
  - OpenClaw pilot host in WSL2 is still below the repo Python 3.13 baseline, so validation truth currently depends on the Windows project `.venv`
- `capacity_model`: `1 architect + 1 coordinator + 2 workers + 1 shared reviewer/debugger`
- `governing_decisions`:
  - `decision_log.md`
  - `docs/mcp-bridge-v1.md`
  - `docs/openclaw-first-work-plan.md`
  - `conventions.md`

## Architect

- `status`: `ACTIVE`
- `current_focus`: `protect the MCP direction as local-only, derived-artifact-first, and Codex-CLI-centered`
- `open_blockers`:
  - no repo-local blocker beyond the active bounded slice queue
- `next_actions`:
  - decide whether to add the first real Codex launch hook or freeze the workflow for Linux migration
  - preserve the boundaries around local task state, direct Codex CLI posture, and no app-thread assumptions
- `go_no_go`: `GO`

## Coordinator

- `status`: `ACTIVE`
- `active_dispatch_id`: `NONE`
- `current_focus`: `hold after MCP-CONTROL-003 and use this state as a migration-readiness checkpoint`
- `open_blockers`:
  - validation still needs the Windows `.venv` workaround while the pilot host remains below baseline
- `next_actions`:
  - keep `MCP-CONTROL-003` closed with repo-native evidence
  - decide GO or NO-GO for the first real Codex launch hook
  - keep the shared reviewer/debugger stateless and slice-based
  - record closure or rework in `workflow/review/` and `workflow/validation/`

## Workers

| worker_id | role | assigned_slice | status | blocker | next_action | evidence_paths |
| --- | --- | --- | --- | --- | --- | --- |
| W1 | mcp control scaffold worker | none | READY | none | wait for a deliberate GO on the first real Codex launch hook | `workflow/outputs/MCP-CONTROL-002_W1.md`; `workflow/outputs/MCP-CONTROL-003_W1.md` |
| W2 | docs/contracts worker | none | READY | none | stay idle unless the next launch-hook decision forces contract clarification | `workflow/outputs/MCP-CONTROL-001_W2.md`; `docs/mcp-bridge-v1.md`; `docs/openclaw-first-work-plan.md` |
| R1 | shared reviewer/debugger | none | READY | none | wait for the next deliberate implementation slice | `workflow/review/MCP-CONTROL-001.md`; `workflow/review/MCP-CONTROL-002.md`; `workflow/review/MCP-CONTROL-003.md` |
