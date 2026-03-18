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

## 2026-03-17 - Antigravity remains blocked on decode or export evidence

Decision:

- treat Antigravity as protobuf-backed but still opaque from outside the application
- do not implement the Antigravity adapter until we have a validated decode path or a documented exported fixture
- treat `brain/` as an artifacts-area clue, not as a proven transcript anchor

Why:

- the installed application bundle explicitly depends on protobuf tooling and embeds trajectory-oriented protobuf models
- the local `.pb` artifacts do not behave like straightforward protobuf messages under lightweight inspection
- building an adapter before the decode or export path is understood would create a fragile provider-specific fork

## 2026-03-17 - Antigravity is policy-gated, not an enabled live provider

Decision:

- treat Antigravity as policy-gated rather than as an enabled provider path
- do not build a live Antigravity adapter over active local session state
- if Antigravity support happens later, start from manual exports or another official provider-approved surface

Why:

- current product direction is based on read-only local compatibility, not on unofficial service access
- provider policy risk is materially higher for Antigravity than for Codex or Claude Code
- this keeps the roadmap conservative, durable, and aligned with the repo's local-first guardrails

## 2026-03-17 - Cross-device continuity stays derived-artifact only

Decision:

- keep experimental cross-device continuity scoped to normalized derived artifacts only
- allow this continuity posture for Codex
- allow this continuity posture for Claude Code only as a complement to official provider flows
- exclude Antigravity from live continuity work unless an official export/API/policy path exists

Why:

- this keeps continuity aligned with the repo's read-only design
- it avoids credential sync, raw-state sync, and unofficial session-cloning behavior
- it is the most conservative path that still preserves cross-device value

## 2026-03-17 - Thin VS Code integration should rely on a tiny documented CLI contract

Decision:

- keep the VS Code extension dependent on a very small extension-facing CLI surface
- document that surface explicitly instead of letting the extension depend on informal behavior
- promote `codex-session-mirror --json` as the machine-readable export completion contract

The intended extension surface is:

- `codex-session-mirror --json`
- `codex-session-list --json`
- `codex-session-open --print`
- `codex-session-handoff --latest --print`

Why:

- this keeps the extension thin and orchestration-focused
- it avoids accidental CLI coupling through undocumented assumptions
- it improves extension-readiness without moving logic out of Python

## 2026-03-18 - Any future bridge should stay above the derived mirror and target Codex CLI first

Decision:

- if this repo grows a bridge for external runtimes such as OpenClaw, keep that bridge optional and local-only
- do not turn the current mirror core into a required daemon, sync engine, or live session backend
- treat Codex CLI as the first supported control surface for bounded external orchestration
- do not assume Codex App or VS Code extension threads are stable external backends

Why:

- the current product thesis is still correct: local-first, read-only, derived-artifact centered
- a bridge can add coordination value without mutating raw Codex state or reintroducing credential-sync behavior
- Codex CLI is a more defensible integration surface than app-thread internals or extension UI state
- this preserves one durable Python core while still creating a path toward OpenClaw and MCP-based interoperability

## 2026-03-17 - VS Code extension readiness should be validated manually before more UI work

Decision:

- prefer a manual Extension Development Host validation pass before adding more extension UI
- document the workspace setup, command checklist, and negative checks explicitly
- keep launch support minimal and local to the extension skeleton

Why:

- the current risk is integration correctness, not missing UI chrome
- the project still wants a thin frontend over the Python core
- manual validation is the fastest way to catch path-resolution and setup issues without expanding scope

## 2026-03-18 - OpenClaw pilot should use a coordinator-plus-workers topology

Decision:

- use one OpenClaw coordinator for dispatch and two narrow workers for code scaffold and docs/contracts
- keep recurring automation disabled for code-writing slices until one manual coordinator-to-worker cycle validates cleanly
- accept a temporary Windows-venv validation workaround while the WSL2 pilot host remains below the repo's Python 3.13 baseline

Why:

- this keeps OpenClaw aligned with a PM/coordinator role instead of turning it into one unconstrained coding agent
- narrow worker scopes reduce drift and make the pilot easier to audit
- the current host mismatch is real, but it should be handled explicitly rather than hidden

## 2026-03-18 - Repo-native workflow surface adopted for MCP work

Decision:

- adopt the standard architect + coordinator + workers workflow directly inside this repo under `workflow/`
- treat this repo as `Tier 1` for workflow review posture
- use one shared reviewer/debugger by default for implementation slices that touch MCP trust boundaries or core contracts

Why:

- the MCP direction is now concrete enough that repo-native coordination artifacts are more durable than keeping all operational state in pilot worktrees
- this keeps the current implementation effort auditable and portable without copying Tuplar's full coordination scale
- a shared reviewer/debugger preserves quality and security pressure without forcing one dedicated debugger per worker at this repo stage

## 2026-03-18 - The first MCP control path should prefer direct Codex CLI and separate local task state

Decision:

- prefer direct Codex CLI invocation for the first bounded control spike instead of ACP wrapping
- keep control-task state outside `out/` in a separate local hidden task-state root
- retain only bounded task metadata and prune terminal task records after `7 days`

Why:

- the first control objective is a small inspectable execution surface, not a second orchestration layer
- keeping task state out of `out/` preserves the distinction between portable derived artifacts and local operational state
- bounded retention limits drift and avoids turning task history into a shadow transcript store

## 2026-03-18 - The first control helper surface should exist before any Codex launch hook

Decision:

- expose enqueue, status, and result helpers over local task-state records before adding any real Codex CLI launch hook
- keep the first control helper surface purely local and record-driven

Why:

- this proves the contract and result surface without mixing in subprocess or runtime failure modes yet
- it lets OpenClaw and future MCP consumers integrate against stable local state before live execution is introduced

## 2026-03-18 - Native Linux is now the preferred next continuation environment

Decision:

- treat the current repo state as the migration-readiness checkpoint
- continue the next serious MCP slice from a native Linux clone rather than from the WSL2 pilot host

Why:

- the repo now contains enough workflow, validation, and handoff structure to move without relying on memory
- the next risk step is the first real Codex launch hook, which is better introduced in the cleaner native Linux environment
- Linux removes the current WSL2 Python-baseline mismatch and reduces operational drift

## 2026-03-18 - Live workflow control surface moved to Portfolio-OS

Decision:

- move the live architect + coordinator + workers workflow package out of this repo and into `Portfolio-OS`
- keep this repo focused on implementation code, tests, technical docs, and thin handoff pointers
- treat `Portfolio-OS/workflow/projects/codex-portable-context/` as the live source of truth for OpenClaw and MCP coordination state

Why:

- `Portfolio-OS` is the structural repo meant to coordinate existing and future serious projects
- keeping workflow state there avoids turning each implementation repo into its own competing control plane
- this preserves a cleaner separation between portfolio governance and product implementation
