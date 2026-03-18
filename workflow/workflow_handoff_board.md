# Workflow Handoff Board

## Operational Rule

1. `workflow_current.md` is the live current-state file.
2. Handoffs here must stay consistent with `workflow_current.md`.
3. Execution state belongs in `workflow_execution_board.md`.
4. Dispatch artifacts must be bounded and reference exact files or modules in scope.

## Ownership Locks

| domain | current_owner | lock_status | lock_updated_utc | notes |
| --- | --- | --- | --- | --- |
| `src/codex_portable_context/mcp/` + `src/codex_portable_context/cli/mcp.py` + `tests/test_mcp_bridge.py` + `tests/test_mcp_task_state.py` + `tests/test_mcp_control.py` | W1 | FREE | `2026-03-18T19:24:46Z` | bounded control helper slice closed; next step is a deliberate launch-hook decision |
| `docs/mcp-bridge-v1.md` + `docs/openclaw-first-work-plan.md` | W2 | FREE | `2026-03-18T19:16:48Z` | docs-only bounded control design is closed |
| `workflow/` | COORDINATOR | LOCKED | `2026-03-18T19:24:46Z` | repo workflow remains the current control surface |

## Handoff Queue

| handoff_id | created_utc | from_role | to_role | priority | domain | status | blocker | next_action | evidence_paths |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HOF-001 | `2026-03-18T18:57:54Z` | PROJECT_OWNER | ARCHITECT | HIGH | MCP bridge | DONE | none | keep the bridge optional, local-only, and Codex-CLI-centered | `docs/mcp-bridge-v1.md`; `docs/openclaw-first-work-plan.md` |
| HOF-002 | `2026-03-18T18:57:54Z` | ARCHITECT | COORDINATOR | HIGH | MCP read-only slice 1 | DONE | none | archive slice closure and queue the next bounded read-only slice | `workflow/dispatch/MCP-DSP-001.md`; `workflow/outputs/MCP-READ-001_W1.md` |
| HOF-003 | `2026-03-18T18:57:54Z` | COORDINATOR | W1 | HIGH | MCP read-only slice 1 | DONE | none | bounded implementation already recorded | `workflow/dispatch/MCP-DSP-001.md`; `workflow/outputs/MCP-READ-001_W1.md`; `workflow/validation/MCP-READ-001.md` |
| HOF-004 | `2026-03-18T18:57:54Z` | COORDINATOR | R1 | MEDIUM | MCP read-only slice 1 | DONE | none | shared review completed with no blocking findings | `workflow/review/MCP-READ-001.md` |
| HOF-005 | `2026-03-18T18:57:54Z` | ARCHITECT | COORDINATOR | HIGH | MCP read-only slice 2 | DONE | none | latest-summary and artifact lookup closure recorded | `workflow/dispatch/MCP-DSP-002.md`; `workflow/outputs/MCP-READ-002_W1.md`; `workflow/review/MCP-READ-002.md` |
| HOF-006 | `2026-03-18T19:10:01Z` | ARCHITECT | COORDINATOR | HIGH | MCP bounded control design | DONE | none | docs-only control design closed with shared review | `workflow/dispatch/MCP-DSP-003.md`; `workflow/outputs/MCP-CONTROL-001_W2.md`; `workflow/review/MCP-CONTROL-001.md` |
| HOF-007 | `2026-03-18T19:16:48Z` | ARCHITECT | COORDINATOR | HIGH | MCP control scaffold | DONE | none | local task-state scaffold closed with shared review | `workflow/dispatch/MCP-DSP-004.md`; `workflow/outputs/MCP-CONTROL-002_W1.md`; `workflow/review/MCP-CONTROL-002.md` |
| HOF-008 | `2026-03-18T19:21:03Z` | ARCHITECT | COORDINATOR | HIGH | MCP control helpers | DONE | none | bounded enqueue-status-result helper slice closed with shared review | `workflow/dispatch/MCP-DSP-005.md`; `workflow/outputs/MCP-CONTROL-003_W1.md`; `workflow/review/MCP-CONTROL-003.md` |

## Handoff Status Legend

1. `PENDING`
2. `ACKED`
3. `IN_PROGRESS`
4. `BLOCKED`
5. `DONE`
