# Antigravity Adapter Brief

## Purpose

This document consolidates the current Antigravity adapter research into one repo-owned brief.

It is intentionally scoped to:

- what appears useful from the external Antigravity research artifacts
- what is still inferred rather than confirmed
- the minimum safe adapter direction for this repo
- what should explicitly wait until fixtures exist

It is not a claim of completed Antigravity support.

## Evidence Basis

This brief is based on:

- the current provider adapter architecture in this repo
- the Antigravity research artifacts created outside the repo under `~/.gemini/antigravity/brain/...`
- a direct local filesystem inspection on this Linux machine
- the existing normalized session model and mirror contract

### What Was Actually Found Locally

Local inspection on this machine found:

- `~/.gemini/antigravity/brain/`
- `~/.gemini/antigravity/conversations/`
- `~/.gemini/antigravity/implicit/`

Important detail:

- the directory under `brain/` that was initially inspected appears to contain the external research artifacts themselves
- the likely real session artifacts found locally were:
  - `~/.gemini/antigravity/conversations/cbb5444b-f7ff-44eb-b5d2-b5916fdb1135.pb`
  - `~/.gemini/antigravity/implicit/dc8db2e8-3c02-4e2e-b0ba-ef41d8ad1323.pb`

These files are binary `.pb` data, not readable text logs.

Observed constraints from local inspection:

- `file` only reported generic binary `data`
- `strings` output was not meaningfully readable
- `protoc` was not installed locally, so no schema-free decode was available

### What Still Comes Only From The External Research Notes

These signals may still be useful, but they are not yet confirmed by the local inspection:

- that `brain/<session-id>/` is the canonical session source
- that files such as `.system_generated/logs/overview.txt` or `terminal_history.txt` are stable transcript anchors
- that Antigravity should be treated primarily as a text-log directory provider

## Important Caution

The external artifacts are useful for direction, but they are not yet sufficient as a design authority on their own.

Reasons:

- they live outside the repo and are not yet versioned here as source material
- they appear to include some confident assumptions without fixture-backed validation
- they assume specific files like `overview.txt` and `terminal_history.txt` are canonical, but local inspection did not confirm those as the real session source
- they propose immediate CLI/provider exposure too early for the current staged roadmap

So the right stance is:

- use the findings as research input
- do not treat them as a release-ready implementation spec yet

## Recommended Provider Identity

Recommended stable provider id:

- `antigravity`

## Current Status

Current repo status:

- no Antigravity adapter is implemented yet
- no Antigravity fixtures exist in this repo yet
- no user-facing provider selector should be added yet
- Antigravity remains a research and planning target, not a supported path

## Likely Storage Shape

What appears likely now is more complex than the original external notes suggested.

Confirmed local top-level areas:

- provider home candidate:
  - `~/.gemini/antigravity`
- observed subareas:
  - `brain/`
  - `conversations/`
  - `implicit/`

Likely interpretations:

- `brain/` may be a workspace/artifact area rather than the canonical conversation store
- `conversations/*.pb` may hold primary session state or transcript data
- `implicit/*.pb` may hold secondary or background conversation state

This means Antigravity may be structurally different from both:

- Codex, which is currently modeled around primary session JSONL files
- Claude Code, which is currently modeled around primary session JSONL files plus related nested subagent logs

## What Seems Plausible

These parts of the external analysis still look directionally plausible:

- session identity probably comes from UUID-like ids
- latest selection may need filesystem timestamps if embedded timestamps are hard to recover
- Antigravity may require more synthesis than Codex or Claude
- tool activity may not be directly available in a single linear transcript form

## What Is Still Too Speculative

These parts should not be treated as settled yet:

- that `brain/` is the canonical source root for real sessions
- that `.system_generated/logs/overview.txt` is the canonical transcript anchor
- that `terminal_history.txt` exists consistently and is the right tool-call source
- whether `conversations/*.pb` or `implicit/*.pb` are the real provider-native session artifacts
- whether the `.pb` files can be decoded without provider-specific tooling or schema knowledge
- that all sessions share the same directory skeleton
- that `cwd`, `cli_version`, or stable timestamps can always be recovered
- that tool activity can be normalized safely in the first pass
- that the provider should be exposed via `--provider antigravity` before fixtures exist

## Adapter Design Recommendation

Antigravity should follow the same staged pattern we used for Claude Code:

1. write the brief first
2. add fixtures second
3. implement a conservative adapter third
4. keep UX unchanged until the adapter is credible

That means:

- do not start from a broad parser that tries to understand every generated file
- do not expose provider-specific commands
- do not expose a user-facing provider selector yet

## Minimum Useful First Pass

The first Antigravity adapter should support only:

1. default path resolution
2. deterministic discovery of the real session source area
3. a conservative primary session anchor selection rule
4. basic transcript/context extraction from the most stable recoverable artifact only
5. derived mirror generation through the existing core

The first pass should explicitly avoid:

- merging every auxiliary file into one giant transcript
- reconstructing every tool call/output from logs
- turning generated artifacts into first-class conversation events too early
- handoff/source enrichment beyond what is clearly stable

## Discovery Recommendation

Because the local evidence now points at binary `.pb` artifacts, the adapter likely needs:

- `default_home_dir()` -> `~/.gemini/antigravity`
- a provisional source-area decision, not just a fixed `brain/` assumption
- `iter_session_files(source_dir)` to yield the real session anchor artifacts once the canonical location is confirmed

Important note:

The current adapter protocol still expects `iter_session_files()` to yield `Path` objects, but it does not require those to be JSONL files.

For Antigravity, a safe first pass may need to yield:

- protobuf-backed session files
- or exported/decoded derivative fixtures created from them

That choice must be made from real fixture evidence, not from the earlier directory-log assumption.

## Primary Open Design Question

Before implementation, we need one answer:

What is the real canonical session source for Antigravity on disk?

Possible answers now include:

- one `.pb` file under `conversations/`
- one `.pb` file under `implicit/`
- a directory under `brain/`
- an exported or derived text/log view produced from those binaries

This now must be answered from fixtures and format inspection, not inference.

## Mapping To The Normalized Model

The first Antigravity adapter should aim for a conservative subset:

- `provider` -> `antigravity`
- `provider_session_id` -> session directory name
- `session_id` -> same as `provider_session_id` in the first pass
- `source_file` -> chosen primary anchor path
- `source_relpath` -> relative path from the configured source root
- `session_timestamp` -> best available stable timestamp, if any
- `updated_at` -> directory or anchor-file `mtime` fallback
- `cwd` -> only when clearly recoverable
- `source` -> `antigravity`
- `model_provider` -> only when clearly recoverable

## Recommended Parsing Posture

The first parser should be conservative and text-oriented.

It should prefer:

- readable user/assistant/context extraction
- stable metadata extraction
- minimal notable events only when clearly identified

It should avoid:

- aggressive tool-call reconstruction
- guessing event semantics from arbitrary generated files
- mixing planning artifacts and transcript artifacts without strong evidence

## Fixture Requirements

Before implementing the adapter, the repo should gain at least one sanitized Antigravity fixture.

Minimum fixture goal:

- one small sanitized representation of a real session source
- enough data to answer:
  - whether the canonical source is `conversations/`, `implicit/`, or `brain/`
  - what acts as the canonical anchor
  - what identifies the session id
  - whether readable user/assistant text is directly recoverable
  - whether timestamps are embedded or need filesystem fallback

Ideal additional fixture:

- one session that includes tool-heavy activity
- one session that includes generated artifacts but limited transcript richness
- one note describing how the source was decoded or sanitized if protobuf is involved

## Recommended Implementation Sequence

1. capture and sanitize one real Antigravity session fixture
2. determine whether the primary source is binary protobuf or a derived text/log surface
3. document the decoding/export assumption used for the fixture
4. define the primary session anchor rule
5. implement a conservative `antigravity` adapter
6. add provider-level tests first
7. add one mirror export test
8. only after that revisit whether user-facing provider selection is warranted

## Recommendation

The next correct step is not direct implementation from the external notes.

The next correct step is:

- bring one real Antigravity fixture into the repo
- determine whether that fixture comes from `conversations/*.pb`, `implicit/*.pb`, or a validated derived export surface
- answer the session-anchor question from evidence
- then implement a conservative adapter just like the Claude Code path
