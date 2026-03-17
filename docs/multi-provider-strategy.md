# Multi-Provider Strategy

## Decision

`codex-portable-context` should evolve into a multi-provider portability tool without losing its current architecture.

That means:

- the Python core remains the system of record
- the VS Code extension remains a thin frontend
- provider-specific behavior moves into adapters inside the Python core
- normalized derived artifacts remain the product center
- experimental cross-device continuity comes later, after provider adapters are stable

The provider roadmap is:

1. polish Codex integration first
2. introduce the provider abstraction layer
3. add Claude Code compatibility
4. add Antigravity compatibility
5. only then design experimental cross-device continuity

## Core Principle

The long-term architecture should look like this:

```text
VS Code extension / other thin UIs
                |
                v
      Python CLI + Python core
                |
                v
        provider adapter layer
                |
                v
 provider-specific source layouts and session data
```

The core idea is simple:

- UIs stay thin
- provider-specific parsing stays in adapters
- the Python core works with normalized session concepts
- mirrors, handoffs, summaries, and future continuity build on normalized artifacts, not raw provider state

## Separation Of Responsibilities

### Python Core

The Python core should own:

- mirror generation
- reader generation
- handoff generation
- summaries
- redaction
- artifact lookup and opening helpers
- normalized session and event models
- provider adapter interfaces
- provider capability handling
- transport-neutral derived outputs
- continuity-safe derived artifacts for future work

The Python core remains the only place where durable product behavior is defined.

### VS Code Extension

The extension should own only:

- commands
- Command Palette actions
- lightweight Quick Pick flows
- opening generated artifacts
- choosing practical flags such as `latest`, `redacted`, or target artifact type
- workspace-aware invocation of the Python CLI
- actionable setup and invocation errors

The extension should not:

- parse provider session files
- generate mirrors or handoffs itself
- reimplement summaries or redaction
- invent provider-specific logic outside the CLI

### Provider Adapters

Provider adapters should own:

- source discovery
- provider-specific path and storage layout handling
- provider-specific session file parsing
- extraction of provider metadata
- normalization of provider messages/events into the shared model
- capability declaration for optional provider features

Adapters are the only provider-specific layer that should understand raw provider formats.

## Explicit Non-Goals

This phase is not:

- a rewrite into provider-specific products
- one extension per provider
- a sync engine
- a search engine
- a resume engine
- a full continuity engine
- an editor lock-in strategy

The project should remain one product with one durable core.

## Minimum Useful Provider Abstraction

The provider abstraction should be explicit and small.

It does not need a large plugin framework.

It needs:

1. a provider identifier
2. discovery hooks
3. parsing/normalization hooks
4. declared capabilities
5. a shared normalized session model

## Proposed Adapter Shape

An adapter should provide at least these responsibilities:

- `provider_id`
  - stable identifier such as `codex`, `claude-code`, or `antigravity`
- `discover_sessions()`
  - find provider session sources from the configured home/source roots
- `load_session_metadata()`
  - extract provider-native identifiers, timestamps, labels, and source paths
- `parse_session()`
  - normalize messages, tool activity, notable events, and session-level metadata
- `latest_sort_key()`
  - expose the preferred recency signal for "latest" behavior
- `capabilities()`
  - declare optional behavior the provider supports cleanly

This can stay as a plain Python interface or small abstract base. It does not need a dynamic plugin registry yet.

## Normalized Session Model

The core should expect provider adapters to normalize into shared concepts such as:

- `provider`
- `session_id`
- `provider_session_id`
- `source_file`
- `source_relpath`
- `session_timestamp`
- `updated_at`
- `title`
- `cwd` when available
- `originator` when available
- `source` when available
- `model_provider` when available
- `cli_version` when available
- normalized event stream

Normalized event kinds should stay practical and close to the existing product:

- `system_message`
- `developer_message`
- `user_message`
- `assistant_message`
- `tool_call`
- `tool_output`
- `notable_event`
- `session_meta`

Not every provider will supply every field. Missing data should be represented as unavailable rather than invented.

## Provider Capability Flags

Providers may expose capability flags such as:

- `supports_tools`
- `supports_reader_html`
- `supports_handoff_source_enrichment`
- `supports_context_sections`
- `supports_redaction_source_context`
- `supports_latest_selection`

Capability flags should not branch the whole product.

They should only let the core adapt small behavior differences cleanly, such as:

- whether a tool activity section is meaningful
- whether extra source-level enrichment is possible
- whether some metadata fields are trustworthy

## Provider-Agnostic vs Provider-Specific Artifacts

### Provider-Agnostic Artifacts

These should remain shared across providers:

- `README.md`
- `index.html`
- `sessions-index.jsonl`
- `metadata/<session-id>.json`
- `sessions/<session-id>.md`
- `reader/<session-id>.html`
- `handoffs/<session-id>.md`
- `handoffs/<session-id>.json`

These are the durable product artifacts.

### Provider-Specific Details

These should stay inside the metadata or normalized model, not in product layout forks:

- provider-native session ids
- provider-native source paths
- provider-specific event mappings
- provider-specific capability declarations
- provider-specific parsing limitations

The mirror layout should not split into separate product trees by provider.

## Roadmap

### Phase 1: Polish Codex Integration

Codex remains the reference adapter.

Goals:

- keep the VS Code extension thin
- close only obvious CLI ergonomics gaps needed for smooth Codex UX
- keep Codex-derived behavior as the normalization reference
- avoid architecture churn while the extension and handoff flows stabilize

Expected outcome:

- Codex remains the known-good provider path
- the current CLI and artifacts become the baseline for adapter behavior

### Phase 2: Introduce The Provider Abstraction Layer

Goals:

- codify a small adapter interface
- introduce a normalized session model inside the Python core
- keep current Codex workflows working unchanged at the CLI surface
- move Codex handling behind the adapter layer without changing product behavior

Expected outcome:

- Codex becomes the first real adapter
- the core stops assuming "Codex" is the only source layout
- the CLI still feels provider-agnostic to end users where possible

### Phase 3: Add Claude Code Compatibility

Goals:

- add a Claude Code adapter against the normalized model
- map Claude Code session discovery and event structure into the shared concepts
- preserve the same artifact outputs as much as possible

Likely easier:

- session discovery if the source layout is file-based and stable
- title/timestamp extraction
- message normalization for user/assistant turns

Likely harder:

- tool activity mapping if the event model differs substantially
- identifying which provider-native fields are truly stable
- source-enriched handoff sections if the raw data is thinner or structured differently

Success means:

- Claude Code can generate the same mirror and handoff artifact families through the same core

### Phase 4: Add Antigravity Compatibility

Goals:

- add an Antigravity adapter using the same normalized model
- keep the provider-specific complexity contained inside the adapter

Likely easier:

- metadata extraction if timestamps/session labels are explicit
- basic transcript normalization

Likely harder:

- mapping tool or system events into the existing normalized event vocabulary
- deciding how much provider-native nuance should be preserved in normalized summaries
- determining whether handoff enrichment can stay as rich as Codex/Claude

Success means:

- Antigravity can produce the same artifact families without forking the product model

### Phase 5: Experimental Cross-Device Continuity

Only after the adapters are stable:

- design continuity on top of normalized mirrors and handoffs
- do not write back into raw provider state
- do not sync credentials
- do not depend on provider-native mutable storage

Continuity should consume normalized, derived artifacts rather than raw live session internals.

## Why Continuity Comes Later

This is not just scheduling preference. It is an architectural safety decision.

Raw provider state differs too much:

- different storage layouts
- different event models
- different metadata guarantees
- different assumptions about "latest", tool activity, and session identity
- different risks around mutability and unsupported write-back

If continuity is attempted before adapters stabilize, the project will drift toward:

- provider-specific hacks
- fragile raw-state assumptions
- inconsistent handoff quality
- editor- or provider-dependent behavior

That is exactly what this architecture is trying to avoid.

The safe path is:

1. normalize providers first
2. stabilize shared artifacts first
3. build continuity on those normalized artifacts later

That keeps continuity:

- transport-neutral
- provider-light rather than provider-fragile
- aligned with the existing local-first, read-only thesis

## CLI Ergonomics Review

The current CLI surface is already a strong base for this roadmap.

Useful capabilities already present:

- `--latest`
- `--redact`
- `--out-dir`
- `--print`
- selector-by-id or prefix where applicable
- `codex-session-list --json`
- `codex-session-open --reader`
- `codex-session-open --handoff`

### Small No-Regret Gaps To Track

These are worth tracking, but they do not justify a large feature block yet:

1. a future `--provider`
   Why:
   once adapters exist, the CLI may need an explicit provider selector when multiple providers are available locally

2. a normalized provider field in machine-readable list outputs
   Why:
   future thin UIs will likely want to label sessions by provider in Quick Picks and tables

3. a tiny extension-facing invocation contract
   Why:
   the VS Code layer should keep depending on a small documented CLI surface, not informal behavior

4. optional future machine-readable exporter completion output
   Why:
   useful for editor UX, but not required before adapters start landing

### What Not To Add Yet

Do not add now:

- `--provider` before the adapter layer exists
- provider-specific command families
- provider-specific artifact layouts
- continuity flags or resume-like switches

## Recommendation

Follow the roadmap in order:

1. polish Codex integration first
2. introduce the adapter layer
3. add Claude Code
4. add Antigravity
5. only then design experimental continuity

That is the cleanest path to a durable multi-provider product without losing the current strengths of `codex-portable-context`.
