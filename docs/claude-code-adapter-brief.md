# Claude Code Adapter Brief

## Purpose

This document captures the first concrete adapter brief for Claude Code.

It is intentionally scoped to:

- confirmed storage and discovery findings
- the minimum viable adapter shape
- what is likely straightforward
- what is still provisional

It is not a claim of completed Claude Code support.

## Current Status

Current repo status after the first implementation pass:

- a conservative `claude-code` adapter now exists in the Python core
- discovery is intentionally limited to primary session JSONL files under `.claude/projects`
- nested subagent logs are intentionally excluded from top-level session discovery
- parsing is fixture-backed and intentionally conservative
- no user-facing `--provider` CLI surface is exposed yet
- shared mirror generation already accepts `provider="claude-code"` internally
- current coverage includes provider-level fixtures and derived mirror export tests

This keeps the integration real enough to validate internally without claiming release-ready Claude Code support.

## Evidence Basis

This brief is based on:

- the current normalized provider architecture in this repo
- a native Windows validation artifact recorded on 2026-03-17
- confirmed local Claude Code session storage findings from a Windows machine

Confirmed findings from that validation:

- Claude Code local sessions were found under:
  - `C:\Users\Alejandro\.claude\projects\`
- primary session logs were stored as JSONL files:
  - `C:\Users\Alejandro\.claude\projects\<project-key>\<session-id>.jsonl`
- subagent logs were stored under:
  - `C:\Users\Alejandro\.claude\projects\<project-key>\<session-id>\subagents\agent-*.jsonl`
- the observed main JSONL log contained fields such as:
  - `sessionId`
  - `cwd`
  - `gitBranch`
  - user / assistant message records
  - `message.content`
  - `file-history-snapshot`
- one observed assistant model value was:
  - `claude-opus-4-6`

## Adapter Positioning

Claude Code should be added as the second real provider adapter after Codex.

The adapter should remain:

- thin
- Python-only
- local-first
- read-only with respect to Claude Code source state

The adapter should not:

- write back into `.claude`
- treat file-history or debug directories as the canonical transcript source
- expose provider-specific product surfaces outside the normalized core

## Proposed Provider Identity

Recommended stable provider id:

- `claude-code`

## Discovery Assumptions

### Confirmed Windows Discovery Root

Confirmed from native Windows findings:

- provider home candidate:
  - `%USERPROFILE%\\.claude`
- primary source root candidate:
  - `%USERPROFILE%\\.claude\\projects`

### Provisional Cross-OS Assumptions

These are reasonable but not yet validated in this repo:

- Linux/macOS provider home:
  - `~/.claude`
- Linux/macOS source root:
  - `~/.claude/projects`

These should remain provisional until confirmed with real local Claude Code data.

## Expected Source Layout

### Primary Session Logs

Expected canonical session source:

- `<projects-root>/<project-key>/<session-id>.jsonl`

Where:

- `<project-key>` appears to be a normalized project-root label
- `<session-id>` appears to be the provider-native session id

### Related Subagent Logs

Expected related source:

- `<projects-root>/<project-key>/<session-id>/subagents/agent-*.jsonl`

Recommendation:

- do not treat subagent logs as top-level sessions
- attach them as related provider-native artifacts or supplementary activity later

For the first Claude adapter pass, it is safer to:

- discover only the primary `<session-id>.jsonl` files
- ignore subagent enrichment unless the relationship is unambiguous

## Minimum Useful Adapter Scope

The first Claude Code adapter should support:

1. default home/source resolution
2. deterministic session discovery
3. source context loading if a stable native index exists
4. parsing of the main session JSONL into the normalized session model
5. latest-session selection using the best available timestamp
6. derived mirror, reader, and handoff generation through the shared core

The first Claude adapter does not need:

- subagent transcript merge
- file-history reconstruction
- debug log ingestion
- provider-specific UI
- continuity/resume behavior

## Mapping To The Normalized Model

The current normalized core expects concepts such as:

- `provider`
- `provider_session_id`
- `session_id`
- `source_file`
- `source_relpath`
- `session_timestamp`
- `updated_at`
- `cwd`
- `model_provider`
- normalized conversation and notable events

### Likely Easy Mappings

Based on the findings, these fields are likely straightforward:

- `provider`
  - fixed as `claude-code`
- `provider_session_id`
  - from `sessionId`
- `session_id`
  - likely identical to `provider_session_id` in the first pass
- `source_file`
  - absolute JSONL path
- `source_relpath`
  - project-relative path under the configured source root
- `cwd`
  - from the observed `cwd` field
- `model_provider`
  - likely `anthropic` when model strings indicate Claude variants
- `updated_at`
  - from the best provider-native timestamp, or file `mtime` fallback

### Likely Moderate Mappings

These need real sample sessions to validate carefully:

- `session_timestamp`
- title derivation
- distinguishing user vs assistant vs system records reliably
- identifying notable lifecycle events
- deciding whether `gitBranch` belongs in normalized metadata now or later

### Likely Harder Areas

These should be treated as later enrichment, not first-pass requirements:

- subagent merge semantics
- file-history snapshots as meaningful context blocks
- any Claude-specific tool or structured action events
- stable source-context enrichment beyond what is clearly present in the primary JSONL

## Proposed Adapter Behavior

### Default Paths

The adapter should eventually provide:

- `default_home_dir()`
- `default_source_dir(home_dir)`

For the first Claude adapter pass:

- use `.claude/projects` as the default source root
- do not inspect debug or cache-style directories by default

### Discovery

The adapter should discover:

- primary session logs matching `*.jsonl` under `<projects-root>`

It should exclude:

- nested `subagents/agent-*.jsonl` as standalone sessions
- auxiliary debug or cache directories

### Session Descriptor

The adapter should produce a `ProviderSessionDescriptor` that at minimum carries:

- `provider`
- `provider_session_id`
- `session_id`
- `source_file`
- `source_relpath`
- best available `updated_at`
- optional session label if a stable provider-native title emerges

### Parsed Session

The adapter should normalize the main JSONL transcript into the existing shared `ParsedSession` shape.

Initial priority:

- user messages
- assistant messages
- basic metadata
- conservative notable events only when the event type is clearly understood

## First-Pass Parsing Rules

The first Claude parser should be conservative.

It should prefer:

- extracting readable user/assistant conversation
- preserving provider-native metadata when stable
- leaving unclear records out of normalized sections rather than inventing meaning

It should avoid:

- over-interpreting provider-specific records
- synthesizing pseudo-tool events from ambiguous data
- merging subagent activity into the main transcript too early

## Recommended Implementation Sequence

1. add a `claude-code` adapter with default path and discovery behavior only
2. add fixture-backed tests using synthetic Claude-style JSONL
3. implement first-pass transcript parsing for main session logs
4. validate mirror output contract remains stable
5. add a small doc pass recording confirmed vs provisional Claude assumptions
6. only then explore subagent enrichment

## Testing Strategy

Because this repo currently has no local Claude Code sessions available, the adapter should be built against:

- fixture-based tests first
- real sample validation later when accessible

Minimum tests for the first adapter:

- default path resolution
- discovery under `.claude/projects`
- exclusion of nested subagent files from top-level session discovery
- `sessionId` mapping into `provider_session_id` and `session_id`
- basic user/assistant transcript normalization
- `cwd` and model metadata extraction when present

## What Is Confirmed vs Provisional

### Confirmed

- Windows storage root under `.claude/projects`
- primary session JSONL placement
- nested subagent JSONL placement
- presence of `sessionId`, `cwd`, `gitBranch`, message content, and file-history snapshot style records

### Provisional

- Linux/macOS path parity
- exact event taxonomy
- exact title derivation strategy
- exact model metadata normalization rules
- how much subagent activity should appear in the first handoff/mirror outputs

## Recommendation

The Claude Code adapter is ready for design and fixture-led implementation, but not for a release-ready support claim yet.

The right next step is:

- implement discovery and conservative transcript normalization
- keep subagents and advanced enrichment explicitly out of scope for the first pass
- validate the adapter against fixtures before claiming compatibility
