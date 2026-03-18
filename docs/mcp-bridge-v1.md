# MCP Bridge v1

## Purpose

Define the first viable bridge layer that lets external runtimes such as OpenClaw consume Codex-derived context and request bounded Codex work without turning `codex-portable-context` into a live session backend.

This is a design note, not a claim that the bridge exists yet.

## Core Decision

If this repo adds an interoperability layer, it should be:

- optional
- local-only by default
- derived-artifact first
- Codex-CLI centered
- explicit about trust boundaries

It should not depend on controlling Codex App threads or VS Code extension UI state.

## Non-Goals

The bridge must not:

- write back into `~/.codex/sessions`
- sync raw `~/.codex`
- copy auth state
- require a background daemon for the core mirror product
- treat Codex App threads as a stable external API
- treat the VS Code extension as a backend
- promise session resurrection across runtimes

## Problem To Solve

Today the repo already provides:

- a read-only derived mirror
- portable session readers
- handoff bundles

What is still missing is a thin interoperability surface so another agent runtime can:

- discover available Codex-derived context
- fetch the latest portable context bundle
- read a selected session summary or transcript
- request bounded Codex work through an official controllable surface
- retrieve the result in a structured, auditable way

## Architectural Position

The bridge sits above the existing Python core.

```text
raw Codex source
        |
        v
provider adapter layer
        |
        v
derived mirror + handoff artifacts
        |
        +--> existing CLI + VS Code extension
        |
        +--> optional local MCP bridge
                 |
                 +--> OpenClaw
                 +--> other MCP-capable local clients
```

The bridge is not a replacement for the mirror.

The mirror remains the source of portable context.

## Why Codex CLI Comes First

The first bounded execution path should target Codex CLI rather than Codex App or the VS Code extension because:

- Codex CLI is a local, explicit runtime
- it already exposes a command surface
- it is more stable to automate than UI threads
- it keeps the trust boundary clearer
- it avoids pretending that a visual conversation thread is an external API

If App or extension integration is explored later, it should be treated as a separate adapter problem.

## v1 Scope

v1 should be small and enforceable.

### v1 Read Tools

The bridge should expose tools equivalent to:

- `list_sessions`
- `get_latest_session_summary`
- `read_session_markdown`
- `read_session_metadata`
- `get_latest_handoff`
- `get_handoff_by_session`
- `list_available_artifacts`

These tools should read from:

- derived mirror artifacts
- derived handoff artifacts
- normalized metadata already owned by this repo

They should not parse provider raw state on every request if the mirror already provides the needed output.

### v1 Bounded Control Tools

The first bounded execution tools should stay narrow:

- `enqueue_codex_prompt`
- `get_codex_task_status`
- `get_last_codex_result`
- `get_last_codex_result_summary`

These tools should target Codex CLI only.

They should not:

- claim to talk to Codex App threads
- claim to talk to VS Code extension threads
- mutate raw session logs directly

## v1 Bounded Control Posture

The first control path should remain narrower than a general agent runtime.

It should be:

- local-only
- Codex-CLI-only
- process-bounded
- auditable through explicit task records
- separated from the derived mirror output tree

The first control spike should prefer direct Codex CLI invocation over ACP wrapping.

Why:

- the first goal is bounded, inspectable execution rather than a second orchestration layer
- direct Codex CLI execution keeps the trust boundary smaller
- ACP can still be added later if the direct CLI path proves too limited

## v1 Control Request / Response Shape

### `enqueue_codex_prompt`

Minimum request shape:

```json
{
  "working_directory": "/abs/path/to/target/repo",
  "prompt": "Do one bounded task.",
  "session_name": "optional-name",
  "model_profile": "optional-profile",
  "execution_mode": "oneshot",
  "timeout_seconds": 900
}
```

Minimum response shape:

```json
{
  "task_id": "mcp-task-20260318-001",
  "status": "queued",
  "accepted_at": "2026-03-18T19:10:01Z",
  "working_directory": "/abs/path/to/target/repo",
  "task_state_path": "/abs/path/to/local/state/mcp-tasks/mcp-task-20260318-001.json"
}
```

Boundaries:

- `working_directory` must be absolute
- `prompt` must be explicit and bounded
- `execution_mode` should start with one conservative value only:
  - `oneshot`
- the response must not imply that a Codex session already exists until one is actually created

### `get_codex_task_status`

Minimum request shape:

```json
{
  "task_id": "mcp-task-20260318-001"
}
```

Minimum response shape:

```json
{
  "task_id": "mcp-task-20260318-001",
  "status": "running",
  "accepted_at": "2026-03-18T19:10:01Z",
  "started_at": "2026-03-18T19:10:05Z",
  "completed_at": null,
  "codex_session_id": null,
  "working_directory": "/abs/path/to/target/repo"
}
```

Allowed status values:

- `queued`
- `running`
- `completed`
- `failed`
- `cancelled`
- `missing`

### `get_last_codex_result`

Minimum request shape:

```json
{
  "task_id": "mcp-task-20260318-001"
}
```

Minimum response shape:

```json
{
  "task_id": "mcp-task-20260318-001",
  "status": "completed",
  "final_text": "Final bounded result text.",
  "codex_session_id": "optional-session-id",
  "artifact_paths": [],
  "result_summary": {
    "outcome": "completed",
    "has_final_text": true
  }
}
```

The first spike should prefer final bounded text plus minimal execution metadata.

It should not try to expose full transcript replay as the control result surface.

## Task State Location And Retention

Control-task state must not live under `out/`.

`out/` remains the portable derived-artifact surface.

The first control path should store state in a separate local hidden task-state root:

- Linux/macOS preferred:
  - `~/.local/state/codex-portable-context/mcp-tasks/`
- Windows preferred:
  - `%LOCALAPPDATA%\\codex-portable-context\\mcp-tasks\\`
- fallback when platform state directories are unavailable:
  - `~/.codex-portable-context/mcp-tasks/`

Task-state files should be:

- local-only
- non-portable
- excluded from git
- small JSON or JSONL records

Retention posture:

- keep active tasks until they reach a terminal state
- completed, failed, or cancelled tasks are eligible for pruning after `7 days`
- the first implementation should keep only:
  - bounded request metadata
  - timestamps
  - task status
  - final result summary
  - optional Codex session id reference

It should not keep:

- auth material
- raw provider session state
- unlimited execution logs by default

## Explicit Control Non-Goals

The first bounded control path must not:

- attach to an already-open Codex App thread
- attach to a VS Code extension conversation thread
- mutate raw provider session files
- become the only supported way to use this repo
- require a remote service or always-on daemon
- claim multi-turn autonomous control

The first justified scope is:

- one bounded request
- one bounded task record
- one bounded result lookup path

## Recommended v1 Tool Contracts

### `list_sessions`

Input:

- optional provider filter
- optional limit
- optional title filter

Output:

- session id
- provider
- title
- timestamp
- available artifact paths

### `get_latest_session_summary`

Input:

- optional provider filter

Output:

- latest session id
- title
- short summary
- mirror artifact paths

### `read_session_markdown`

Input:

- session id or unique prefix

Output:

- transcript markdown path
- transcript content or chunk reference

### `get_latest_handoff`

Input:

- optional provider filter

Output:

- handoff path
- handoff content
- linked session metadata

### `enqueue_codex_prompt`

Input:

- working directory
- prompt text
- optional session name
- optional model or config profile
- bounded execution mode

Output:

- task id
- Codex session id if created
- accepted timestamp

### `get_codex_task_status`

Input:

- task id

Output:

- queued, running, completed, failed, or missing
- timestamps
- last known session id

### `get_last_codex_result`

Input:

- task id or session id

Output:

- raw final text output
- artifact paths if generated
- minimal execution metadata

## Security Boundaries

The bridge must follow these rules:

- local-only by default
- explicit opt-in if remote access ever exists
- no credential transport
- no implicit execution on behalf of the user
- no default write-back into provider state
- no hidden trust between runtimes

If a control tool can cause Codex to execute work, that tool must be:

- explicit
- bounded
- auditable
- separable from read-only artifact access

## Packaging Direction

Keep the bridge inside the same Python repo only if it stays a thin optional layer.

Recommended shape:

- Python package remains primary
- bridge lives under `src/codex_portable_context/mcp/`
- local entrypoint such as:
  - `python -m codex_portable_context.cli.mcp_server`
  - or `codex-session-mcp`

Important:

- the mirror and handoff CLIs remain usable without the bridge
- MCP should be an additive integration surface, not a new product center

## v1 Execution Model

Preferred runtime model:

- process-per-use or user-started local server
- no always-on daemon requirement for normal mirror usage

This keeps the current README true in spirit:

- the core product still does not require a daemon or backend
- the bridge is an optional local interface for advanced workflows

## Suggested Implementation Order

1. Define the bridge contract in docs.
2. Reuse existing mirror and handoff artifact readers.
3. Add read-only MCP tools first.
4. Add a small task registry for bounded Codex CLI orchestration.
5. Add Codex CLI execution hooks only after the read-only path is stable.
6. Document the trust boundary and validation path before calling it usable.

## Open Questions

- Should result retrieval prefer transcript summaries, final assistant text, or both?
- Should a redacted mirror be the only allowed source for some remote or shared bridge modes later?

## Success Criteria

The bridge is useful only if all of these are true:

- mirror-only usage remains intact
- no raw Codex state is mutated
- OpenClaw or another client can fetch derived context without scraping app state
- bounded Codex work can be enqueued and polled through a stable local surface
- the bridge does not force a background service on users who only want mirror exports
