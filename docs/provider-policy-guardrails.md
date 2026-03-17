# Provider Policy Guardrails

## Purpose

This document defines provider-level guardrails for `codex-portable-context`.

It is intentionally product-facing, not legal advice.

Its job is to keep the repo aligned with a conservative implementation posture:

- one Python-first core
- read-only handling of local provider state
- derived mirrors and handoffs as the portability surface
- no credential sync
- no write-back into live provider state

Cross-device continuity-specific guardrails are documented in [cross-device-continuity-guardrails.md](./cross-device-continuity-guardrails.md).

## Product Rule

Providers are not all equal from a policy and integration standpoint.

The repo therefore uses three provider postures:

- `enabled`
  - provider-local read-only adapters are acceptable
- `caution`
  - read-only compatibility is acceptable, but should remain complementary to official product flows
- `policy-gated`
  - do not build a live provider adapter unless an official API, export surface, or explicit policy allowance exists

## Provider Matrix

### Codex

Status:

- `enabled`

Allowed:

- read local provider state to build derived mirrors
- generate handoff bundles and other derived artifacts
- open and browse derived outputs locally or on another device
- use the VS Code extension as a thin local orchestrator over the Python CLI

Caution:

- treat raw session files as implementation details, not a stable public API
- keep cross-device continuity scoped to normalized derived artifacts, not raw state

Avoid:

- syncing `~/.codex` as live state
- copying or sharing `auth.json` except where the provider's own documentation explicitly allows it and the user knowingly accepts the risk
- treating credentials or runtime caches as portability artifacts

### Claude Code

Status:

- `caution`

Allowed:

- generate derived mirrors and handoffs from local data
- use the same normalized artifact model as Codex where feasible
- present compatibility as complementary to the provider's official VS Code and continuity flows

Caution:

- do not present this repo as a replacement for official Remote Control or other first-party continuity features
- treat provider-native state as unstable unless fixture-backed and clearly local

Avoid:

- reimplementing official continuity/remote-control semantics
- claiming account-level or cloud-level session continuity from local-only artifacts
- syncing credentials or live mutable provider state

### Antigravity

Status:

- `policy-gated`

Allowed:

- manual import of user-exported artifacts
- analysis of manually exported or otherwise officially exposed derived files
- normalized handling of those manual artifacts after they are outside the live service boundary

Caution:

- any future support must start from an official export path, documented API, or explicit policy allowance
- opaque local storage should not be treated as automatically safe to parse just because it exists on disk

Avoid:

- live adapters that access or depend on active Antigravity session state
- reverse-engineering local session storage into a first-class provider path
- OAuth, login reuse, or third-party service access patterns
- promising Antigravity as a supported parity provider today

## Action Matrix

### Allowed

- build derived mirrors from local Codex data
- build derived mirrors from local Claude Code data
- generate handoffs from normalized local data
- move only derived artifacts across devices
- keep the VS Code extension thin and local

### Caution

- parse local provider-specific transcripts and metadata when those formats are not documented as stable
- expose provider compatibility before fixture-backed validation exists
- infer continuity semantics from local storage layouts alone

### Avoid

- credential sync
- write-back into provider session stores
- raw-state sync engines
- live service access through unofficial provider integrations
- treating Antigravity as an enabled provider before an official export/API/policy path exists

## Roadmap Implication

These guardrails imply:

1. Codex remains the primary enabled provider.
2. Claude Code remains the next compatibility target.
3. Antigravity is not an enabled live-adapter target today.
4. If Antigravity support happens later, it should start as manual-export compatibility, not as direct session access.
5. Cross-device continuity should continue to build on normalized derived artifacts only.
