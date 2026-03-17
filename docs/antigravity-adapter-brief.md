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
- the existing normalized session model and mirror contract

Useful signals from the external artifacts:

- Antigravity likely stores session data under:
  - `~/.gemini/antigravity/brain/<session-id>/`
- the session unit appears directory-based rather than single-file JSONL
- candidate provider-native materials may live under paths such as:
  - `.system_generated/logs/overview.txt`
  - `.system_generated/logs/terminal_history.txt`
- the adapter will likely need to synthesize normalized events from multiple files instead of replaying one monolithic transcript log

## Important Caution

The external artifacts are useful for direction, but they are not yet sufficient as a design authority on their own.

Reasons:

- they live outside the repo and are not yet versioned here as source material
- they appear to include some confident assumptions without fixture-backed validation
- they assume specific files like `overview.txt` and `terminal_history.txt` are canonical, but that has not yet been verified in this repo through stable fixtures
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

The research strongly suggests a directory-based session layout:

- provider home candidate:
  - `~/.gemini/antigravity`
- source root candidate:
  - `~/.gemini/antigravity/brain`
- one session per directory:
  - `~/.gemini/antigravity/brain/<session-id>/`

This would make Antigravity structurally different from:

- Codex, which is currently modeled around primary session JSONL files
- Claude Code, which is currently modeled around primary session JSONL files plus related nested subagent logs

## What Seems Plausible

These parts of the external analysis look directionally plausible:

- session identity probably comes from the UUID-like directory name
- latest selection may need directory/file timestamps rather than provider-native transcript timestamps
- logs and artifacts may need to be aggregated from several files
- tool activity may be reconstructable from generated logs
- the adapter will likely need a more synthetic parser than Codex or Claude

## What Is Still Too Speculative

These parts should not be treated as settled yet:

- that `.system_generated/logs/overview.txt` is the canonical transcript anchor
- that `terminal_history.txt` exists consistently and is the right tool-call source
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
2. deterministic session discovery from `brain/<session-id>/`
3. a conservative primary session anchor selection rule
4. basic transcript/context extraction from the most stable file(s) only
5. derived mirror generation through the existing core

The first pass should explicitly avoid:

- merging every auxiliary file into one giant transcript
- reconstructing every tool call/output from logs
- turning generated artifacts into first-class conversation events too early
- handoff/source enrichment beyond what is clearly stable

## Discovery Recommendation

Because Antigravity appears directory-based, the adapter likely needs:

- `default_home_dir()` -> `~/.gemini/antigravity`
- `default_source_dir(home_dir)` -> `home_dir / "brain"`
- `iter_session_files(source_dir)` to yield one stable anchor per session directory

Important note:

The current adapter protocol still expects `iter_session_files()` to yield `Path` objects, but it does not require those to be JSONL files.

For Antigravity, a safe first pass may yield:

- the session directory itself
- or one clearly designated anchor file within the session directory

The choice should be made only after fixture inspection.

## Primary Open Design Question

Before implementation, we need one answer:

What is the most stable primary session anchor inside one Antigravity session directory?

Possible answers:

- the directory itself
- one canonical text log
- one metadata file plus auxiliary logs

This should be answered from fixtures, not inference.

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

- one small session directory under `tests/fixtures/antigravity/<session-id>/`
- enough data to answer:
  - what acts as the canonical anchor
  - what identifies the session id
  - where readable user/assistant text lives
  - whether timestamps are embedded or need filesystem fallback

Ideal additional fixture:

- one session that includes tool-heavy activity
- one session that includes generated artifacts but limited transcript richness

## Recommended Implementation Sequence

1. capture and sanitize one real Antigravity session fixture
2. add a repo-owned fixture note describing the observed layout
3. define the primary session anchor rule
4. implement a conservative `antigravity` adapter
5. add provider-level tests first
6. add one mirror export test
7. only after that revisit whether user-facing provider selection is warranted

## Recommendation

The next correct step is not direct implementation from the external notes.

The next correct step is:

- bring one real Antigravity fixture into the repo
- answer the session-anchor question from evidence
- then implement a conservative adapter just like the Claude Code path
