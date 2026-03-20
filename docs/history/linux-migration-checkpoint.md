# Linux Migration Checkpoint

Date: 2026-03-18

## Purpose

Capture the repo-specific state that makes `codex-portable-context` ready to continue from a native Linux clone.

This note is preserved as historical checkpoint context only. The in-repo MCP surface described here has since been removed after the split to `agent-bridge`.

## Why This Repo Is Ready Enough To Move

The workflow is no longer just pilot glue.

This repo now has:

- a bounded workflow package now owned by `Portfolio-OS` under `workflow/projects/codex-portable-context/`
- shared-review closure on each serious slice

That is enough structure to migrate without relying on memory.

## Linux Success Criteria

The Linux continuation is considered aligned only if:

- Python `3.13+` is used natively
- the live workflow state in `Portfolio-OS/workflow/projects/codex-portable-context/workflow_current.md` still matches the repo implementation checkpoint
- no WSL-only workaround is needed for validation

## First Post-Migration Decision

After Linux validation, decide one of these explicitly:

- `GO`: continue the next core implementation slice from native Linux
- `HOLD`: stop at the current product checkpoint and harden packaging or validation first

Do not drift into implementation before making that explicit decision.
