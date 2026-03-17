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
- a direct local inspection of the installed Antigravity application bundle on this Linux machine
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

### What Was Confirmed From The Installed Application

Local inspection of the installed application found:

- `/usr/bin/antigravity` launches the packaged application bundle
- the packaged bundle lives under `/usr/share/antigravity/resources/app/`
- the bundle explicitly depends on:
  - `@bufbuild/protobuf`
  - `@exa/proto-ts`

The compiled bundle also confirms that Antigravity stores app data under:

- `~/.gemini/antigravity`

This comes from bundled helpers that resolve the app data root from:

- `[".gemini", ideName]`

and from bundled path-segment constants such as:

- `userSettingsFilePathSegments: ["user_settings.pb"]`
- `artifactsDirPathSegments: ["brain"]`
- `knowledgeItemsPathSegments: ["knowledge"]`
- `mcpConfigFilePathSegments: ["mcp_config.json"]`

This is stronger evidence than the earlier external notes because it comes from the installed product itself.

### What Was Confirmed About Internal Data Modeling

The application bundle contains generated protobuf code for at least one Gemini Coder trajectory model:

- `../exa/proto_ts/out/dist/exa/gemini_coder/proto/trajectory_pb.js`

That generated code includes message names such as:

- `Conversation`
- `ConversationState`
- `Trajectory`
- `Step`

and fields such as:

- `conversation_id`
- `trajectory_id`
- `cascade_id`
- `steps`
- `metadata`

This does not prove that the local `.pb` session artifacts are direct serialized `Trajectory` messages, but it does confirm that protobuf-backed conversation and trajectory concepts are first-class inside the application.

### What Was Confirmed About The Local `.pb` Files

The local `.pb` files currently look opaque from outside the application.

Observed behavior:

- no gzip header
- no common zlib header
- not meaningfully readable through `strings`
- a lightweight protobuf wire-format probe does not walk them cleanly as straightforward protobuf messages

That means the `.pb` files may be:

- wrapped in an additional container format
- compressed with a non-trivial encoding
- encrypted or authenticated
- or serialized in a way that is not directly useful without the app's own decode path

For this repo, the important conclusion is simple:

- we should not assume `conversations/*.pb` or `implicit/*.pb` are directly parseable fixtures yet

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
- Antigravity is policy-gated and should not be treated as an enabled live provider

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
- `brain/` is also explicitly referenced by the installed app as an artifacts directory, which makes it more likely to be derived or auxiliary than a clean transcript anchor

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
- whether the `.pb` files are plain protobuf messages at all, rather than wrapped or protected containers
- that all sessions share the same directory skeleton
- that `cwd`, `cli_version`, or stable timestamps can always be recovered
- that tool activity can be normalized safely in the first pass
- that the provider should be exposed via `--provider antigravity` before fixtures exist

## Adapter Design Recommendation

Antigravity should not follow the same implementation path as Codex or Claude Code unless an official export, API, or policy-allowed compatibility surface exists.

For now, the correct staged pattern is:

1. write the brief first
2. gather evidence second
3. confirm an official or clearly user-exported compatibility surface third
4. only then decide whether an adapter is appropriate at all

That means:

- do not start from a broad parser that tries to understand every generated file
- do not expose provider-specific commands
- do not expose a user-facing provider selector
- do not build a live adapter over active local session state

## Minimum Useful First Pass

If Antigravity support happens later, the first pass should be manual-export compatibility only.

That first pass should support only:

1. importing a user-exported or otherwise officially exposed artifact
2. deterministic discovery of the exported source area
3. a conservative primary session anchor selection rule
4. basic transcript/context extraction from the most stable recoverable artifact only
5. derived mirror generation through the existing core

That first pass should explicitly avoid:

- merging every auxiliary file into one giant transcript
- reconstructing every tool call/output from logs
- turning generated artifacts into first-class conversation events too early
- handoff/source enrichment beyond what is clearly stable
- direct live-state parsing of opaque local provider storage

## Discovery Recommendation

Because the local evidence now points at binary `.pb` artifacts, any future compatibility layer likely needs:

- a manual-export or official-export input root
- a provisional source-area decision, not just a fixed `brain/` assumption
- `iter_session_files(source_dir)` to yield the real session anchor artifacts once the canonical location is confirmed

Important note:

The current adapter protocol still expects `iter_session_files()` to yield `Path` objects, but it does not require those to be JSONL files.

For Antigravity, a safe first pass may need to yield:

- officially exported session files
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

At this point, "format inspection" should mean one of:

- a validated decode path from the installed application
- an official export or debug path from Antigravity itself
- a repo-owned sanitized derivative fixture with its decode provenance documented

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

The first parser should be conservative and evidence-led.

It should prefer:

- readable user/assistant/context extraction when a decoded source exists
- stable metadata extraction
- minimal notable events only when clearly identified

It should avoid:

- aggressive tool-call reconstruction
- guessing event semantics from arbitrary generated files
- mixing planning artifacts and transcript artifacts without strong evidence
- direct parsing of opaque `.pb` files without a validated decode or export path

## Fixture Requirements

Before implementing any compatibility layer, the repo should gain at least one sanitized Antigravity fixture.

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
2. determine whether the primary source is binary protobuf or a validated derived export surface
3. document the decoding or export assumption used for the fixture
4. identify whether the app itself exposes the canonical anchor as conversation, trajectory, or another container
5. define the primary session anchor rule
6. confirm that the resulting path stays inside provider policy guardrails
7. implement compatibility only if that surface is official or user-exported
8. add provider-level tests first
9. add one mirror export test
10. only after that revisit whether user-facing provider selection is warranted

## Recommendation

The next correct step is not direct implementation from the external notes or from opaque local storage.

The next correct step is:

- bring one real Antigravity fixture into the repo
- determine whether that fixture comes from an official export, a user-exported artifact, or another validated derived surface
- answer the session-anchor question from evidence
- then decide whether manual-export compatibility is appropriate at all
