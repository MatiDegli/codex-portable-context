# Mirror Contract

## Purpose

This document freezes the v1 mirror contract as the compatibility baseline for the planned Python v2 migration.

The goal is to preserve the product behavior while changing the implementation base from Bash to Python. Unless a strong reason is documented, v2 should keep this contract compatible.

## Contract Scope

This contract covers the derived mirror under an output directory such as `out/` or `out-redacted/`.

Primary files:

- `README.md`
- `index.html`
- `sessions-index.jsonl`
- `metadata/<session-id>.json`
- `reader/<session-id>.html`
- `sessions/<session-id>.md`
- `.codex-session-mirror-state.jsonl`

The source of truth remains local Codex session data under `~/.codex/sessions`. The mirror is derived output only.

## Output Layout

Required layout:

```text
<out-dir>/
├── README.md
├── index.html
├── sessions-index.jsonl
├── metadata/
│   └── <session-id>.json
├── reader/
│   └── <session-id>.html
├── sessions/
│   └── <session-id>.md
└── .codex-session-mirror-state.jsonl
```

Invariants:

- `README.md` is a generated landing page for the derived mirror.
- `index.html` is a generated browser reader landing page for the same derived mirror.
- `sessions-index.jsonl` is newline-delimited JSON, one object per exported session.
- `metadata/<session-id>.json` is the per-session structured export.
- `reader/<session-id>.html` is the per-session static HTML reader page.
- `sessions/<session-id>.md` is the readable transcript export for the same session id.
- `.codex-session-mirror-state.jsonl` is local mirror bookkeeping, not part of Codex source state.

## Session Identity

`session_id` is the stable primary key inside the derived mirror.

Invariants:

- each exported session object must include `session_id`
- metadata and transcript paths are keyed by `session_id`
- index entries and metadata entries for the same session should carry the same `session_id`
- transcript filenames and metadata filenames should remain derived from `session_id`

## sessions-index.jsonl

Role:

- machine-readable index for helper CLIs
- stable input to the generated landing page
- summary layer over per-session metadata

Format:

- UTF-8 JSONL
- one JSON object per session
- newest session ordering is not guaranteed by file order; consumers should sort by exported timestamp fields

### Stable Required Fields

These fields should remain present for each index entry:

- `provider`
- `session_id`
- `title`
- `export_profile`
- `exported_at`
- `source_relpath`
- `metadata_relpath`
- `markdown_relpath`
- `redacted`
- `markdown_includes`
- `summary`
- `redaction_report`

At least one usable timestamp field should also be present:

- `updated_at`
- or `session_timestamp`
- or both

### Stable Optional Fields

These fields are useful and should be preserved when available, but may be `null`:

- `provider_session_id`
- `thread_name`
- `updated_at`
- `session_timestamp`
- `cwd`
- `originator`
- `source`
- `model_provider`
- `cli_version`
- `reader_relpath`

### Stable Count Fields

These fields should remain numeric when present:

- `event_count`
- `context_entry_count`
- `user_message_count`
- `assistant_message_count`
- `tool_call_count`
- `tool_output_count`
- `notable_event_count`

## metadata/<session-id>.json

Role:

- full structured export for one derived session
- compatibility anchor for helper commands and future Python core logic

### Required Fields

The metadata file should carry the same stable fields as the index entry:

- `provider`
- `session_id`
- `title`
- `export_profile`
- `exported_at`
- `source_relpath`
- `metadata_relpath`
- `markdown_relpath`
- `redacted`
- `markdown_includes`
- `summary`
- `redaction_report`

### Optional Fields

These fields should remain compatible when available:

- `provider_session_id`
- `thread_name`
- `updated_at`
- `session_timestamp`
- `cwd`
- `originator`
- `source`
- `model_provider`
- `cli_version`
- `source_file`
- `reader_relpath`

### Markdown Filter Notes

`markdown_filter_rules` is part of the exported metadata contract.

Invariants:

- it should remain an array of strings
- it documents conservative readability filtering, not source mutation

## summary Object

Role:

- mechanical per-session summary for landing pages, list views, and future lookup helpers

### Required Fields

- `preview`
- `activity`
- `environment`
- `detail_line`
- `one_line`

### Optional Fields

- `first_user_message`
- `last_user_message`
- `last_assistant_message`

### Summary Invariants

- summary values are derived mechanically from session content
- summary values are not AI-generated summaries
- `preview` is intended for short reading-oriented views
- `detail_line` combines activity and environment information
- `one_line` is a compact compatibility field for existing helpers

## redaction_report Object

Role:

- audit hint for best-effort redaction applied to derived output only

### Required Fields

- `enabled`
- `best_effort`
- `note`
- `artifacts`
- `placeholder_totals`
- `total_replacements`

### Required Nested Fields

Under `artifacts`, both of these should exist:

- `metadata`
- `markdown`

Each artifact object should include:

- `placeholder_counts`
- `rule_counts`
- `total_replacements`

### Redaction Invariants

- redaction is best-effort, not guaranteed DLP
- redaction applies only to derived output
- redaction report counts are audit hints, not proof of full detection

## sessions/<session-id>.md

Role:

- readable transcript export for one session

The exact prose may evolve, but the conceptual sections should remain compatible:

- metadata
- session snapshot
- export notes
- session context when included
- conversation
- notable events when included

### Markdown Invariants

- Markdown is optimized for reading, not lossless raw replay
- routine low-value records may be omitted conservatively
- profile flags affect derived Markdown sections only
- raw source files remain untouched

## reader/<session-id>.html

Role:

- browser-friendly static reader page for one exported session

Expected behavior:

- generated from the same derived mirror output as the Markdown and metadata
- safe to move together with the mirror
- links back to `../index.html`, `../README.md`, `../sessions/<session-id>.md`, and `../metadata/<session-id>.json`
- may present the transcript as escaped preformatted text instead of fully rendered Markdown

## README.md in the Mirror Root

Role:

- self-contained landing page for copied or synced mirrors

Expected behavior:

- generated from the derived index, not from raw `~/.codex`
- relative links to transcript and metadata files
- mirror-level summary
- start-here guidance for the newest session

## index.html in the Mirror Root

Role:

- self-contained browser landing page for copied or synced mirrors

Expected behavior:

- generated from the derived index, not from raw `~/.codex`
- links to `reader/<session-id>.html`, `sessions/<session-id>.md`, and `metadata/<session-id>.json`
- includes mirror-level summary and lightweight client-side filtering

## .codex-session-mirror-state.jsonl

Role:

- local incremental export state for the derived mirror

Format:

- UTF-8 JSONL
- one JSON object per source-relative session file

Required fields per line:

- `source_relpath`
- `input_signature`
- `session_id`
- `metadata_relpath`
- `markdown_relpath`

State invariants:

- this file is mirror-local bookkeeping only
- it is not part of Codex source state
- it may change more freely than the public mirror files, but field compatibility should be preserved where practical

## Compatibility Guidance for v2

Preferred path for Python v2:

- preserve file layout
- preserve field names and field roles
- preserve summary and redaction object shapes where practical
- preserve helper expectations around `sessions-index.jsonl`

Allowed changes only with explicit justification:

- adding new optional fields
- tightening invariants when it improves portability
- minor wording changes in generated Markdown that do not break file roles

Changes that should be treated as format breaks:

- renaming or removing stable required fields
- changing `session_id` path derivation
- replacing JSONL with a different index/state format
- changing helper-facing path semantics without a compatibility layer
