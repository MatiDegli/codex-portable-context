# Linux Migration Checkpoint

Date: 2026-03-18

## Purpose

Capture the repo-specific state that makes `codex-portable-context` ready to continue from a native Linux clone.

## Why This Repo Is Ready Enough To Move

The workflow is no longer just pilot glue.

This repo now has:

- a repo-native workflow surface under `workflow/`
- a bounded read-only MCP bridge
- a bounded local task-state scaffold
- bounded enqueue/status/result helpers over task-state records
- shared-review closure on each serious slice

That is enough structure to migrate without relying on memory.

## Current MCP Surface

Implemented:

- `session_list`
- `get_latest_session_summary`
- `session_artifacts_get`
- `session_handoff_get`
- `enqueue_codex_prompt`
- `get_codex_task_status`
- `get_last_codex_result`

Still intentionally missing:

- any real Codex CLI launch hook
- any daemon or always-on service behavior
- any Codex App or VS Code thread control path

## Linux Success Criteria

The Linux continuation is considered aligned only if:

- Python `3.13+` is used natively
- the MCP-focused tests pass on Linux
- `codex-session-mcp --help` works after editable install
- the repo workflow state still matches `workflow/workflow_current.md`
- no WSL-only workaround is needed for validation

## First Post-Migration Decision

After Linux validation, decide one of these explicitly:

- `GO`: implement the first real Codex CLI launch hook
- `HOLD`: stop at the current helper surface and harden packaging or validation first

Do not drift into implementation before making that explicit decision.
