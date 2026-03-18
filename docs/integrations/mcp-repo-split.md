# MCP Repo Split

## Purpose

Define the safest split between `codex-portable-context` and a future dedicated MCP/orchestration repo.

This document exists because two different product directions are easy to blur together:

- a thin local bridge over derived artifacts
- a separate orchestration product for OpenClaw and future runtime control

They should not be treated as the same repo concern.

## Core Recommendation

Keep `codex-portable-context` as:

- the Python-first system of record
- the owner of mirror, handoff, metadata, and reader artifacts
- the owner of stable local CLI contracts over those artifacts

Create a separate repo for:

- an MCP server or runtime-facing orchestration surface
- OpenClaw integration
- bounded Codex execution orchestration
- any future experiments involving Codex Extension threads or Codex App threads

## Why Split

`codex-portable-context` is intentionally:

- local-first
- read-only with respect to provider source state
- artifact-centered
- usable outside any one editor or control runtime

An orchestration-focused MCP product is materially different:

- it becomes runtime-facing rather than artifact-facing
- it may need lifecycle, task execution, or process supervision
- it is more likely to accumulate provider- or client-specific control logic
- it is likely to be published and versioned as a separate integration tool

Keeping them together would blur the repo's product boundary and make this repo feel like a control plane again.

## What Stays In `codex-portable-context`

The core repo should continue to own:

- provider discovery and normalization
- derived mirror generation
- handoff generation
- reader generation
- artifact lookup and open flows
- the stable CLI contracts that outside tools can consume

The preferred external contract surface remains:

- `codex-session-mirror --json`
- `codex-session-list --json`
- `codex-session-open --print`
- `codex-session-handoff --print`

Those commands are the cleanest dependency surface for another repo.

## What Moves To The New MCP Repo

The dedicated MCP/orchestration repo should own:

- MCP server shape
- OpenClaw-facing protocol and runtime
- bounded task orchestration
- process supervision and runtime state
- any future adapters for Codex CLI control
- any future research into Codex Extension or Codex App thread communication

If thread-oriented control is explored later, it should be isolated there rather than introduced as a hidden second product inside this repo.

## Current In-Repo MCP Status

The current in-repo MCP code is best understood as a transitional scaffold.

Useful pieces that may inform the new repo:

- `src/codex_portable_context/mcp/task_state.py`
- `src/codex_portable_context/mcp/control.py`
- `docs/integrations/mcp-bridge-v1.md`

Less suitable for direct extraction as-is:

- `src/codex_portable_context/mcp/bridge.py`
- `src/codex_portable_context/cli/mcp.py`

Why:

- they still depend directly on the internal Python core
- they are better treated as a temporary local bridge than as the final public MCP product boundary

## Safe Migration Sequence

### Phase 1

Keep the current MCP code in this repo only as a local transitional bridge.

Do not expand it toward:

- extension-thread control
- app-thread control
- daemonized orchestration
- published runtime integration

### Phase 2

Create the dedicated MCP repo with a narrow initial contract:

- depend on installed `codex-portable-context`
- call the stable CLI contracts
- treat `codex-sync` outputs as the source of truth

### Phase 3

Move or re-implement runtime concerns there:

- task lifecycle
- server protocol
- OpenClaw integration
- bounded execution orchestration

Only after that should the in-repo transitional MCP surface be evaluated for deprecation or removal.

## Packaging Recommendation

The first new repo should package itself as an orchestration tool, not as a fork of `codex-portable-context`.

Recommended dependency posture:

- install `codex-portable-context` normally
- consume its CLI contracts and artifact outputs
- avoid importing deep internal `codex_portable_context.core.*` modules as a public dependency strategy

This keeps the boundary cleaner and reduces cross-repo breakage.

## Non-Goals

This split should not:

- turn `codex-portable-context` into a hidden library-only dependency with no CLI value
- move mirror or handoff ownership out of this repo
- make OpenClaw the architectural center of this repo
- imply that Codex Extension or Codex App threads are stable backends today
