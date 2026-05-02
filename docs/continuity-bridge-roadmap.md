# Continuity Bridge Roadmap

## Purpose

This roadmap moves handoff bundles from a useful operational snapshot toward a stronger continuity bridge for fresh-session re-entry.

The goal is not to recreate, resume, or mutate a live provider session. The goal is that a new local session can start from derived artifacts and quickly recover:

- what the prior conversation was trying to accomplish
- what was decided
- what changed
- what remains unresolved
- what should happen next
- which details are evidence and which are inferred

## Current Gap

The current handoff bundle is good at preserving a local-first audit trail:

- session identity and artifact links
- current-state heuristics
- recent normalized actions
- recent conversation window
- recent notable events and tool calls
- operational risks such as a dirty repo or missing source session

It is weaker as a cognitive re-entry bridge for long conversations.

In long architecture or coordination sessions, the most important state is often not in the final tool call. It is in the accumulated decisions, repo boundaries, invariants, rejected paths, and user preferences that shaped the work. A fresh session should not need to read a huge transcript just to recover that mental model.

## Current Implementation Snapshot

Status as of the Phase 5h consolidation pass:

- Phases 1 through 5h are implemented in the Python handoff generator, Markdown renderer, reader integration, and audit CLI.
- `codex-session-handoff --restart-prompt` emits a copy-ready fresh-session prompt.
- The static reader exposes a copy button for the generated restart prompt.
- `codex-session-handoff-audit` reports readiness, purpose, quality gates, prompt compliance, memory counts, role hints, and evidence sources.
- Recent real-sample audit over 20 sessions: `7 ready`, `1 review`, `0 weak`, `12 minimal_expected`, `0 error`.
- Prompt compliance over the same sample: `20 pass`, `0 review`, `0 fail`, `0 error`.
- Active sessions are intentionally review-gated until their turns are resolved.
- Bootstrap/ACK sessions are now classified as `minimal_expected` instead of polluting weak continuity counts.

E2E restart prompt trial:

- Three fresh agents were initialized from real restart prompts: architecture/boundary, implementation follow-up, and bootstrap reviewer.
- The implementation follow-up and bootstrap reviewer prompts produced correct first responses: no tools, recovered context, inferred posture, candidate next steps, and mode confirmation.
- The architecture/boundary prompt initially stayed safe but collapsed to only a mode question.
- The restart prompt now includes a required first-response format to make context recovery explicit; the architecture/boundary retest produced the expected structured response.
- Active in-progress prompts now use a context-recovery next action rather than a generic continuation action; an E2E trial confirmed the prompt did not use tools or start implementation.
- Static prompt compliance checks now verify the first-response contract, required response format, confirmation gate, first-turn tool ban, and safe first action without initializing agents.
- Manual E2E manifests can now be generated with `codex-session-handoff-audit --write-e2e-manifest <path>`; this writes prompts, formal result templates, and evaluation rubrics but does not launch agents.
- The local `agent-bridge-public` MCP surface supports bounded send/receive in this environment, but cannot create new threads, so fresh-agent E2E trials currently use local subagents.

Validation commands for this snapshot:

```bash
./scripts/validate-python-v2
.venv/bin/codex-session-handoff-audit --out-dir ./out --limit 20
.venv/bin/codex-session-handoff-audit --out-dir ./out --limit 3 --write-e2e-manifest ./out/restart-prompt-e2e.json
```

## Local Memory Investigation

The first implementation pass checked local Codex state for compaction and memory signals.

Findings:

- `event_msg` records with `type=context_compacted` exist in source JSONL files, but current observed payloads are empty.
- `turn_context.summary` is present structurally, but observed values are `none`.
- `response_item` records with `type=reasoning` carry `encrypted_content`; observed `summary` arrays are empty.
- `state_5.sqlite` contains a `stage1_outputs` table with promising fields such as `raw_memory` and `rollout_summary`, but it is currently empty in the inspected local state.
- `state_5.sqlite` also contains `thread_spawn_edges`, which links parent sessions to spawned child sessions. This is a useful local continuity source for long delegated sessions.

Implications:

- visible compaction summaries should be consumed when present, but handoff generation must not depend on them always existing
- encrypted reasoning content should be treated as unavailable to the local derived-artifact flow
- linked child session summaries are the next high-value local signal to bring into handoffs
- the Python stdlib SQLite reader is sufficient for local enrichment; installing the `sqlite3` CLI is optional for manual inspection only

## Guardrails

This roadmap keeps the existing continuity safety model:

- derived artifacts only
- no raw `~/.codex` sync
- no credential sync
- no write-back into provider state
- no provider-specific resume claims
- no hidden server or daemon requirement
- no LLM dependency for the baseline path
- source excerpts must remain traceable to local artifacts

Any semantic enrichment must be conservative and auditable. If a field is inferred by heuristics, the handoff should say so or keep the underlying evidence nearby.

## Target Shape

The ideal handoff should keep the existing audit trail, but add a top layer optimized for re-entry:

1. `Continuation Brief`
2. `Resolved State`
3. `Decisions and Invariants`
4. `Changed Artifacts`
5. `Open Loops and Risks`
6. `Restart Prompt`
7. `Evidence Trail`

The lower sections can remain verbose. The top section should be compact enough to paste into a fresh Codex session without dragging in the entire transcript.

## Phase 1: Continuation Brief

Add a first-class `continuation_brief` object to `handoff.json` and a matching Markdown section near the top.

Initial implementation status: `continuation_brief` is now emitted in JSON and Markdown from deterministic transcript/state signals. It is still intentionally extractive and should improve as later phases add stronger changed-artifact and decision extraction.

Minimum fields:

- `what_we_were_doing`
- `why_it_mattered`
- `latest_resolved_request`
- `last_meaningful_outcome`
- `next_best_action`
- `do_not_do`
- `confidence`
- `evidence`

Implementation guidance:

- Prefer exact recent user and assistant text when possible.
- Promote the final assistant answer over the final test command when identifying the outcome.
- Treat a question as resolved when later assistant output clearly reports implementation, validation, or a commit.
- Use explicit provider compaction summaries or prompts when they are present in source events.
- Keep the current `Current State` section until the new field proves better.

Acceptance checks:

- A developer can read only `Continuation Brief` and know the next action.
- The brief does not contradict `Recent Actions`, `Open Loops`, or repo state.
- The JSON and Markdown contain the same core brief.

## Phase 2: Resolved State

Separate "last user request" from "state after the request was handled".

Initial implementation status: `resolved_state` is now emitted in JSON and Markdown. It distinguishes `answered`, `handled_with_changes`, `unanswered`, `blocked`, `derived_only`, and `unknown`, prevents answered question-style requests from being shown as open questions, and expands short context-dependent follow-ups such as `Pasamelo` with the previous substantive request.

Add or refine fields:

- `latest_user_request`
- `contextual_user_request`
- `request_resolution_status`
- `resolution_summary`
- `validation_summary`
- `commit_summary`
- `dirty_state_summary`
- `remaining_local_only_paths`

Implementation guidance:

- Detect recent commits from source CWD when available.
- Include commit hash, commit subject, and changed-file count when safe.
- Detect dirty paths and group them as tracked, untracked, ignored if practical.
- Distinguish product changes from local dogfood, mirror, or workflow artifacts when the transcript provides that evidence.

Acceptance checks:

- A completed task no longer appears as an open question solely because the last user message was phrased as a question.
- `last_meaningful_outcome` names the human outcome, not just the last validation command.
- Dirty repo warnings identify what is dirty enough for a fresh session to act carefully.

## Phase 3: Decisions and Invariants

Extract durable conversation memory from long sessions.

Initial implementation status: `changed_artifacts` extracts changed/key paths and a recommended inspection order from recent text, tool outputs, and git status. `decisions_and_invariants` now extracts durable statements, invariants, rejected paths, and open architecture questions from high-signal recent context. Deeper repo-boundary and project-vocabulary extraction remains pending.

Add a `decisions_and_invariants` object:

- `decisions`
- `repo_boundaries`
- `invariants`
- `rejected_paths`
- `key_artifacts`
- `open_architecture_questions`
- `project_vocabulary`
- `confidence`
- `evidence`

Implementation guidance:

- Start with deterministic extraction from transcript headings and high-signal phrases:
  - `Strategic decisions already made`
  - `Stable boundary`
  - `Non-goals`
  - `Do not`
  - `must not`
  - `source of truth`
  - `public boundary`
  - `support matrix`
- Prefer explicit transcript statements over inferred summaries.
- Keep each item short and link or quote a small evidence excerpt.
- Avoid over-extracting every repeated term; the section should contain durable memory, not search results.

Acceptance checks:

- Architecture sessions preserve repo ownership boundaries without requiring the full transcript.
- A fresh session can avoid already-rejected directions.
- Items are traceable to transcript or metadata evidence.

## Phase 4: Restart Prompt

Generate a copy-ready fresh-session prompt from the structured handoff fields.

Initial implementation status: `restart_prompt` is now emitted in JSON and Markdown as a deterministic fresh-session re-entry prompt. It includes session identity, repo state, continuation brief, resolved state, open loops, child-session references, artifact links, and an explicit first action. It also includes `reentry_posture`, which defaults the first turn to read-only context retrieval and review, with confirmation required before commands, tests, or file edits.

The prompt should include:

- session title and ID
- repo root and branch
- continuation brief
- decisions and invariants
- changed artifacts and validation status
- open loops and risks
- exact first action
- artifact links for deeper inspection

Implementation guidance:

- Keep this prompt local and deterministic.
- Make it clear that it is a re-entry prompt, not a session resume.
- Make the first turn read-only by default.
- Keep it compact enough for normal use, with links to the full handoff and transcript.

Acceptance checks:

- The prompt can be pasted into a new Codex session and produce a coherent first response.
- The prompt does not require source-machine credentials.
- The prompt does not ask the destination session to mutate provider session state.

## Phase 4a: Linked Child Sessions

Use local thread relationship data to include bounded summaries of spawned child sessions.

Initial implementation status: handoff generation now reads `state_5.sqlite` when present, extracts child rows from `thread_spawn_edges` plus `threads`, and renders a `Linked Child Sessions` section in both JSON and Markdown. This remains optional local enrichment.

Minimum fields:

- `parent_session_id`
- `child_session_id`
- `status`
- `title`
- `cwd`
- `rollout_path`
- `first_user_message`
- `latest_assistant_message`
- `updated_at`

Implementation guidance:

- Treat `state_5.sqlite` as optional local enrichment.
- Read it only when present and only for derived handoff generation.
- Do not require SQLite state for portable handoff consumption.
- Keep child summaries compact and link to their own mirror/handoff artifacts when available.
- Prefer existing mirror metadata for child session summaries when the child has already been exported.

Acceptance checks:

- Long parent sessions that delegated work show the relevant child sessions near the top-level continuity context.
- Missing SQLite state degrades gracefully.
- Child session data does not replace the parent transcript or child transcript as evidence.

## Phase 5: Reader and CLI Ergonomics

Expose the continuity bridge without turning the static reader into a backend app.

Initial implementation status: `codex-session-handoff --restart-prompt` prints only the generated fresh-session prompt, `codex-session-handoff` refreshes the per-session reader with an embedded copyable restart prompt, and `codex-session-handoff-audit` samples selected handoffs, regenerates them by default, and reports `Decisions / Invariants` coverage, confidence, sources, role hints, and quality flags such as `no_memory` and `low_confidence`. This gives the bridge a fast paste path and a repeatable quality check before deeper reader ergonomics.

Possible improvements:

- show whether a handoff exists before linking to it when the mirror can know that
- add CLI flags:
  - `codex-session-open --handoff --print`
  - `codex-session-latest --handoff --print`
- consider a generated `handoffs/<session-id>.prompt.md`

Implementation guidance:

- The Python core remains the source of truth.
- The VS Code extension should call CLI commands, not re-render handoffs.
- The static HTML reader must not pretend it can create files without a local backend.

Acceptance checks:

- Users do not click dead handoff links without guidance.
- The fastest path to a fresh-session restart is obvious from the CLI and reader.
- Extension behavior remains a thin wrapper over the Python CLI.

## Phase 5b: Restart Prompt Quality Gates

Implementation status: implemented.

Move from "prompt exists" to "prompt is good enough to paste without reading the full transcript first".

Add handoff-audit quality gates:

- `missing_restart_prompt`
- `missing_role_hint`
- `prompt_maybe_truncated`
- `no_memory`
- `low_confidence`
- `generic_next_action`
- `bare_recommended_artifacts`
- `missing_validation_summary`
- `dirty_repo_without_paths`
- `prompt_missing_first_response_contract`
- `prompt_missing_required_first_response_format`
- `prompt_missing_confirmation_gate`
- `prompt_missing_first_turn_tool_ban`
- `prompt_first_action_missing_confirmation_wait`
- `prompt_unsafe_first_action`

Add a readiness classification:

- `ready`: prompt can normally be pasted as-is
- `review`: prompt is usable but should be checked against the handoff first
- `weak`: prompt is likely missing important continuity memory
- `error`: handoff artifact could not be read or parsed

Implementation guidance:

- Keep gates deterministic and explainable.
- Treat gates as advisory quality signals, not hard failures.
- Make the JSON report richer than the terminal table.
- Prefer specific flags over a single opaque score.
- Use real handoff samples to tune false positives.

Acceptance checks:

- `codex-session-handoff-audit` identifies low-value prompts without opening each handoff.
- A prompt with missing memory, missing role, or truncated restart text is not marked `ready`.
- Bare filename-heavy artifact lists are flagged for review.

## Phase 5c: Review and Findings Memory Extraction

Implementation status: implemented.

Improve continuity for reviewer/audit sessions where durable memory is expressed as findings rather than decisions.

Extract conservative memory from headings such as:

- `Findings`
- `Resolved during review`
- `Notes`
- `Residual Risks`
- `Residual Test Gaps`
- `Open Questions`
- `Recommendation`
- `Recommended Next Step`
- `Blockers`

Implementation guidance:

- Prefer bullets and numbered findings under explicit headings.
- Preserve severity labels such as `Critical`, `High`, `Medium`, and `Low` when present.
- Route risks, blockers, and residual gaps into open architecture questions or risks.
- Route recommendations into decisions or next-step candidates.
- Do not treat every paragraph in a review as durable memory.

Acceptance checks:

- Reviewer sessions preserve actionable findings in the handoff.
- Residual risks survive into the restart prompt.
- Findings extraction does not pollute ordinary chat sessions.

## Phase 5d: Specific Next Action Synthesis

Implementation status: implemented.

Move `next_best_action` from a generic continuation instruction to a concrete re-entry action.

Inputs, in priority order:

- unresolved failures and expected validation commands
- open architecture questions, residual risks, and blockers
- explicit recommendations or recommended next steps
- conversation/tool-output artifact paths
- git-status paths as fallback only

Implementation guidance:

- Prefer a specific risk/recommendation over artifact inspection.
- Prefer conversation and tool-output paths over incidental dirty repo paths.
- Keep the action short enough to survive inside the restart prompt.
- Treat generic actions as an audit smell via `generic_next_action`.

Acceptance checks:

- Handoffs with enough memory are not flagged with `generic_next_action`.
- The action names the leading risk, recommendation, or artifact to inspect first.
- Unrelated local dirty paths do not displace stronger handoff-specific artifacts.

## Phase 5e: Artifact Path Resolution and Cleanup

Implementation status: implemented.

Reduce low-value artifact recommendations caused by bare filenames or malformed Markdown path fragments.

Implementation guidance:

- Preserve exact paths when tool output already reports a path.
- Resolve bare filenames against the repo root only when there is a unique match.
- Do not guess when multiple repo files share the same basename.
- Drop malformed Markdown fragments and root-only paths.
- Omit bare duplicates when a qualified path with the same basename is already known.
- Treat bare `__init__.py` as too ambiguous for recommended inspection order.

Acceptance checks:

- `bare_recommended_artifacts` decreases on real handoff audits.
- Recommended inspection order prefers `src/...`, `tests/...`, or docs paths over basenames.
- Ambiguous filenames remain conservative instead of pointing at the wrong file.

## Phase 5f: Session Purpose and Audit Calibration

Implementation status: implemented.

Separate poor continuity from sessions that are intentionally minimal.

Classify handoff audit items by purpose:

- `substantive_work`
- `review_or_audit`
- `active_in_progress`
- `bootstrap_or_ack`
- `transport_test`
- `empty_or_noise`

Add readiness:

- `minimal_expected`: session is sparse by design, so missing memory is not a bridge failure

Implementation guidance:

- Keep substantive work and reviewer/audit sessions accountable for memory.
- Treat bootstrap, ACK, handshake, and transport-test sessions as minimal when their only flags are expected sparsity.
- Do not hide real artifact or prompt corruption behind `minimal_expected`.
- Show purpose counts in the audit summary so the dashboard explains why weak counts moved.

Acceptance checks:

- Bootstrap and ACK sessions without durable memory are marked `minimal_expected`.
- Substantive sessions without memory remain `weak`.
- Audit output explains purpose distribution alongside readiness distribution.

## Phase 5g: Restart Prompt Hygiene

Implementation status: implemented.

Remove noisy or misleading prompt content before testing re-entry behavior.

Implementation guidance:

- Filter terminal/runtime noise such as shell cache logs and progress ratios.
- Prefer repo-relative artifact paths for files under the detected repo root.
- Preserve absolute paths only when they point outside the repo and are still meaningful.
- Avoid artifact-driven next actions for bootstrap, ACK, and transport initialization sessions.
- Keep `next_best_action` short enough to avoid truncation in restart prompts.

Acceptance checks:

- Bootstrap handoffs do not tell the next session to inspect cache logs.
- Recommended artifacts inside the repo render as `src/...`, `tests/...`, or docs paths.
- Restart prompts remain untruncated after hygiene changes.

## Phase 5h: Implementation Outcome Memory Extraction

Implementation status: implemented.

Preserve what changed conceptually after implementation turns, not only which files changed.

Extract conservative memory from implementation summaries such as:

- `Implemented and committed ...`
- `Behavior now:`
- `What changed:`
- `Contract:`
- `Known caveat:`
- `Not implemented:`
- `Follow-up:`
- `Remaining:`

Implementation guidance:

- Treat new behavior and implementation summaries as decisions.
- Treat explicit contracts as invariants.
- Treat caveats, remaining work, blockers, and follow-ups as open questions or risks.
- Skip `Changed:` file-only sections because artifact extraction already owns paths.
- Skip validation command bullets because `validation_summary` already owns them.
- Do not turn implementation outcomes into next-action recommendations unless they are explicitly recommendations.

Acceptance checks:

- Substantive implementation sessions with behavior summaries are not marked `weak`.
- `decisions_and_invariants.evidence` includes `implementation_outcome` when extracted.
- Restart prompts preserve behavior-level outcomes without duplicating validation commands.

## Phase 5i: Manual E2E Restart Prompt Manifest

Implementation status: implemented.

Make E2E restart-prompt trials repeatable without making normal audit runs launch agents.

Implementation guidance:

- `codex-session-handoff-audit --write-e2e-manifest <path>` writes a manual-only JSON manifest for the selected sessions.
- The manifest includes each restart prompt, the handoff identity, readiness, prompt compliance status, expected first-response behavior, pass criteria, result status values, `manual_run_summary`, and per-case `manual_result` templates.
- The command must not create threads, send messages, run commands in target repos, or edit files.
- Manual runners paste each `restart_prompt` into a fresh agent/thread and stop after the first response.
- Prompt compliance remains the fast static gate; E2E manifests are the explicit manual layer above it.

Acceptance checks:

- A manifest can be generated from selected handoff audit items without launching agents.
- The manifest declares `manual_only` mode and records that it does not launch agents or send messages.
- Generated cases include the full restart prompt and a rubric for no-tools/no-implementation first responses.
- Generated manifests expose a stable result schema with `not_run`, `pass`, `fail`, and `blocked` status values.

## Phase 6: Provider-Agnostic Continuity Quality

Implementation status: pending.

Keep the new bridge fields provider-neutral.

Checklist:

- Codex handoffs populate all bridge sections when local source is available.
- Claude Code handoffs can populate the same schema from normalized artifacts where possible.
- Missing provider data degrades gracefully with clear `source_availability` notes.
- The schema does not depend on Codex-only event names for its public contract.

Acceptance checks:

- Consumers can read the same JSON keys across providers.
- Provider-specific extraction remains behind adapters.
- The handoff remains useful when only derived mirror data exists, even if less rich.

## Validation Strategy

Use real handoffs as fixtures for qualitative and regression checks.

Suggested fixtures:

- a short completed coding task
- a long architecture session
- a session with an unresolved failure
- a session with dirty repo state
- a redacted mirror
- a mirror where source files are unavailable

Core checks:

- generated Markdown contains the bridge sections
- generated JSON contains stable structured fields
- restart prompt is present and compact
- completed tasks do not become false open questions
- dirty state is described concretely
- redaction still applies to new sections
- missing source sessions degrade gracefully

## Rollout Order

1. Add schema fields and Markdown rendering for `continuation_brief`.
2. Improve resolved-state detection and outcome selection.
3. Add changed-artifact, commit, and dirty-state summaries.
4. Add conservative decisions and invariants extraction.
5. Add restart prompt generation.
6. Improve reader and CLI discoverability.
7. Validate with Codex fixtures.
8. Recheck Claude Code compatibility.

## Non-Goals

This roadmap does not authorize:

- live provider session resume
- raw provider state import or export
- credential movement
- browser-based local file writes
- a required local web server
- account-level continuity claims
- untraceable semantic summaries as the only source of truth

## Success Definition

The continuity bridge is successful when `handoffs/<session-id>.md` alone is enough for a fresh local session to start productively, while the transcript remains available for exact detail.

For long sessions, the new session should recover the durable mental model without reading the entire transcript first.
