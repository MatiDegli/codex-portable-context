# Codex Continuity Bundle

## Purpose

This document defines the minimum Codex continuity bundle for experimental cross-device re-entry.

It is intentionally narrow:

- Codex only
- derived artifacts only
- no raw `~/.codex` sync
- no credential movement
- no live session cloning

## Continuity Goal

The goal is not to recreate a live Codex session.

The goal is to let a developer move from device A to device B and confidently start a fresh local session with enough context to continue work.

## Bundle Profiles

### Single-Session Bundle

Use this when the destination machine only needs one session.

Required:

- `metadata/<session-id>.json`
- `handoffs/<session-id>.json`
- `handoffs/<session-id>.md`
- `sessions/<session-id>.md`

Recommended:

- `reader/<session-id>.html`

Why:

- `handoff.md` is the fastest human re-entry artifact
- `handoff.json` is the stable machine-readable continuity artifact
- `metadata.json` is the structured session facts layer
- `session.md` is the full transcript fallback when detail matters
- `reader.html` gives a portable browser-friendly view

### Mirror Bundle

Use this when the destination machine may need to browse or choose between multiple sessions.

Required:

- `sessions-index.jsonl`
- `metadata/<session-id>.json`
- `handoffs/<session-id>.json`
- `handoffs/<session-id>.md`
- `sessions/<session-id>.md`

Recommended:

- `README.md`
- `index.html`
- `reader/<session-id>.html`

Why:

- `sessions-index.jsonl` provides latest/session selection context
- `README.md` and `index.html` provide portable entry points

## Continuity Entry Artifacts

The bundle should be consumed in this order on the destination machine:

1. `handoffs/<session-id>.md`
2. `handoffs/<session-id>.json`
3. `metadata/<session-id>.json`
4. `sessions/<session-id>.md`
5. `reader/<session-id>.html` when available

This keeps re-entry fast while preserving an auditable path down to the full transcript.

## Destination-Side Workflow

The exact re-entry workflow should be:

1. open `handoffs/<session-id>.md`
2. read:
   - `Continuation Brief`
   - `Resolved State`
   - `Changed / Key Artifacts`
   - `Decisions / Invariants`
   - `Re-Entry Posture`
   - `Restart Prompt`
   - `Recent Actions (normalized)`
   - `Open Loops / Risks`
3. confirm the intended next step
4. open `sessions/<session-id>.md` only if more detail is needed
5. start a fresh local Codex session on the destination machine
6. carry over only the derived context that is needed for the new session

This is a `resume-like` workflow, not a raw resume.

## Minimum Re-Entry Questions

The bundle is good enough only if the destination developer can answer these quickly:

- what was the current focus?
- what was the last meaningful outcome?
- what should happen next?
- what is still unresolved?
- where is the full transcript if deeper detail is needed?

## Acceptance Checks

The Codex continuity bundle is acceptable when:

- `handoff.md` alone gives a clear restart point
- `handoff.json` contains the same core state in machine-readable form
- the full transcript remains available as fallback
- the bundle can be copied independently of `~/.codex`
- the destination workflow never requires source-machine credentials

## Explicit Non-Goals

This bundle must not become:

- a session clone format
- a transport for `auth.json`
- a raw `.codex` snapshot
- a provider-specific resume protocol

## Recommended Next Step

After this bundle shape is accepted:

- verify whether current handoff fields are sufficient in real Codex device-to-device usage
- only then decide whether any low-risk continuity-specific UX polish is needed

The current field review found that operational handoffs are useful but not yet enough for long-session cognitive re-entry. The follow-up roadmap is [Continuity Bridge Roadmap](./continuity-bridge-roadmap.md).
