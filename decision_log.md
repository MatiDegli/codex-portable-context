# Decision Log

## 2026-03-15 - v1 product thesis frozen

Decision:

- treat the Bash implementation as the v1 baseline
- keep the project local-first and read-only
- keep the derived mirror as the core product output

Why:

- the project already reached a useful, coherent v1 state
- expanding scope before validating usage would weaken clarity

## 2026-03-15 - Python chosen for v2

Decision:

- move the long-term implementation core to Python

Why:

- the project now needs Windows native support and real cross-OS portability
- extending the Unix-heavy Bash stack would create a fragile split implementation

## 2026-03-15 - Contract-first migration

Decision:

- freeze the mirror contract before deeper Python implementation work

Why:

- v2 should preserve product behavior while changing implementation base
- explicit contract control reduces accidental output drift

## 2026-03-16 - Python runtime baseline set to 3.13

Decision:

- baseline development target: Python 3.13
- supported target: Python 3.13+

Why:

- align with the Python version strategy already used in Tuplar
- allow newer host Python versions without forcing the OS itself to use Python 3.13

## 2026-03-16 - Pre-Phase-3 repo baseline adopted

Decision:

- add a local authority file
- add a decision log
- add a canonical Python bootstrap path
- add a canonical Python validation path
- add a minimal Python quality baseline with Ruff, MyPy, and pytest

Why:

- improve quality, consistency, and safety before porting the exporter in Phase 3

## 2026-03-16 - Python promoted to primary path, Bash reduced to wrappers

Decision:

- make Python the primary implementation path for v2
- convert the Bash command entrypoints into thin compatibility wrappers
- preserve the last full Bash implementation historically in git

Why:

- parity and cross-OS hardening were strong enough to stop carrying two active implementation cores
- a single Python core is more scalable and maintainable than indefinite Bash/Python duplication

## 2026-03-16 - Python-first install story kept intentionally small

Decision:

- use editable install plus console entrypoints as the main Python usage path
- keep `python -m codex_portable_context.cli.<command>` as a fallback
- keep Bash only as a transitional compatibility layer

Why:

- this gives Linux and Windows users one coherent command model without adding heavy packaging machinery
- it keeps the project easy to understand for a solo developer while still feeling like a serious Python-first tool

## 2026-03-17 - VS Code extension kept as a thin frontend

Decision:

- keep the Python CLI as the system of record
- design any future VS Code extension as a thin orchestration layer
- do not duplicate mirror or handoff logic in TypeScript

Why:

- the current architecture already gives the project a cross-platform, editor-independent core
- a thin extension can improve developer UX without reintroducing a second implementation path

## 2026-03-17 - Initial VS Code extension skeleton added

Decision:

- add a minimal workspace extension skeleton that only orchestrates the Python CLI
- keep the first implementation in plain JavaScript without a build step

Why:

- this is enough to validate the thin-extension direction with low maintenance cost
- the extension can already cover the smallest useful UX surface without introducing a TypeScript or webview-heavy stack

## 2026-03-17 - Multi-provider roadmap staged after Codex polish

Decision:

- keep Codex as the reference provider first
- introduce a provider adapter layer before adding other providers
- add Claude Code next
- add Antigravity after that
- postpone experimental cross-device continuity until provider adapters are stable

Why:

- this preserves one durable Python core instead of drifting into provider-specific products
- normalized adapters are a safer foundation for future continuity than raw provider state

## 2026-03-17 - Adapter layer started with Codex as the first concrete provider

Decision:

- introduce the minimal provider adapter and registry shape now
- wire the current Codex path through that layer without changing CLI UX
- add `provider` to derived metadata/index entries as preparation for future multi-provider flows

Why:

- this begins the provider abstraction with low risk and low churn
- future providers can build on the same derived artifact model instead of forking the product surface

## 2026-03-17 - Claude Code planning should stay evidence-led

Decision:

- plan the Claude Code adapter from confirmed storage and transcript findings first
- treat Windows `.claude/projects` findings as valid discovery evidence
- keep Linux/macOS assumptions and subagent handling provisional until validated

Why:

- this keeps the next provider adapter grounded in real observed data instead of speculation
- it reduces the risk of overdesigning the Claude integration before fixture-backed parsing exists

## 2026-03-17 - Claude Code starts with a conservative fixture-backed adapter

Decision:

- add the first `claude-code` adapter now
- keep discovery limited to primary `.claude/projects/<project-key>/<session-id>.jsonl` files
- exclude nested subagent logs from top-level session discovery for now
- keep the first parser conservative and fixture-backed
- do not expose a new user-facing provider switch yet

Why:

- this makes the Claude path concrete without overclaiming compatibility
- it preserves one stable UX while letting the provider layer mature under tests first

## 2026-03-17 - Antigravity should start from fixtures, not inferred logs

Decision:

- treat the external Antigravity notes as research input only
- do not implement the Antigravity adapter directly from those notes
- require repo-owned sanitized fixtures before choosing the primary session anchor or exposing any provider surface

Why:

- the current Antigravity notes are useful but still inference-heavy
- a directory-based provider is more fragile to over-assume than Codex or Claude Code
- fixture-led implementation is the safer way to keep the adapter conservative and maintainable

## 2026-03-17 - Local Antigravity evidence points to binary session artifacts

Decision:

- treat the local Antigravity `.pb` files under `conversations/` and `implicit/` as the strongest current evidence of real session storage
- downgrade the earlier `brain/` text-log assumption to provisional research only
- require a decoded or sanitized fixture before any adapter implementation starts

Why:

- local inspection found real-looking session artifacts in binary `.pb` files, not readable text logs
- implementing against the earlier `brain/` assumption now would likely target the wrong source surface
