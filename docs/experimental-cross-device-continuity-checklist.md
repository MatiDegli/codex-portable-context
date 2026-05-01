# Experimental Cross-Device Continuity Checklist

## Purpose

This checklist turns the continuity guardrails into a practical implementation sequence.

It is intentionally narrow:

- derived-artifact continuity only
- Codex first
- Claude Code second
- no raw-state sync
- no credential sync
- no write-back into provider session stores

## Scope

This phase should deliver only:

- a portable handoff flow
- a repeatable mirror-to-handoff continuity workflow
- enough metadata and UX to restart work confidently on another device

This phase should not deliver:

- live session cloning
- provider resume semantics
- account-level or cloud-level continuity
- cross-provider session merging

## Preconditions

Before implementation starts:

- the mirror contract remains frozen or explicitly updated
- provider policy guardrails remain unchanged
- continuity work stays provider-agnostic at the artifact level
- the source of truth remains the Python core

## Phase 1: Codex-Only Experimental Continuity

### Checklist

- define the exact continuity entry artifact set:
  - `sessions-index.jsonl`
  - `metadata/<session-id>.json`
  - `handoffs/<session-id>.json`
  - `handoffs/<session-id>.md`
  - `sessions/<session-id>.md`
  - `reader/<session-id>.html` when available
- define the minimum "resume-like" bundle contents needed on the destination device
- define the exact destination-side workflow:
  - inspect handoff
  - inspect transcript if needed
  - start a new provider session
  - re-enter work from normalized context
- define acceptance checks for "good enough continuity":
  - current focus is obvious
  - next action is obvious
  - open loops are obvious
  - supporting artifacts are easy to open

### Deliverable

- one documented Codex-only continuity workflow that stays fully inside derived artifacts
- one explicit Codex bundle definition:
  - [Codex Continuity Bundle](./codex-continuity-bundle.md)

## Phase 2: Continuity Readiness Gaps

### Checklist

- review whether current handoff fields are sufficient for re-entry
- identify missing fields only if they are low-risk and provider-agnostic
- prefer extracting stable facts over adding narrative synthesis
- verify that `codex-session-open` and `codex-session-handoff` already cover the destination-side lookup flow cleanly
- use [Continuity Bridge Roadmap](./continuity-bridge-roadmap.md) as the implementation plan for stronger fresh-session re-entry

### Good Candidate Gaps

- stronger `Current State`
- clearer `Next recommended action`
- better `Open Loops / Risks`
- a more explicit continuity entry section in the reader
- continuation brief
- resolved request state
- durable decisions and invariants
- copy-ready restart prompt

## Phase 3: Thin UX Improvements

### Checklist

- keep CLI as the system of record
- only add small helper UX if it reduces friction materially
- prefer:
  - `--print`
  - stable JSON outputs
  - clear open targets
  - lightweight VS Code commands
- avoid adding a continuity-specific UI before the artifact flow itself feels solid

### Deliverable

- continuity-friendly CLI and reader ergonomics, not a new product surface

## Phase 4: Claude Code Experimental Continuity

This phase should begin only after:

- the Codex continuity flow feels stable
- the Claude adapter remains fixture-backed but credible
- the same continuity model still works from normalized artifacts without provider-specific branching

### Checklist

- confirm Claude-derived handoffs contain enough normalized context
- confirm no OAuth or account-level workaround is required
- keep the workflow complementary to official Claude features
- reuse the same artifact contract used by Codex whenever possible

## Explicit Exclusions

Do not add during this phase:

- raw provider-state sync
- token or credential movement
- provider-specific "resume" semantics
- Antigravity continuity
- background agents or daemons
- server-side continuity infrastructure

## Acceptance Criteria

This experimental phase is complete when:

- one developer can move from device A to device B using only derived artifacts
- the destination-side re-entry path is documented and repeatable
- the workflow does not require credentials from the source machine
- the workflow does not modify provider session stores
- the same conceptual flow works for Codex and appears viable for Claude Code

## Next Step After Completion

After this checklist is complete:

- review whether the experimental flow is genuinely useful in daily work
- only then decide whether to add small UX polish
- do not widen scope into raw resume or provider-specific session cloning
