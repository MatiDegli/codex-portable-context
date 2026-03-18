# VS Code Extension Invocation Contract

## Purpose

This document defines the small CLI surface that the thin VS Code extension may depend on.

It exists so the extension can stay orchestration-only while the Python CLI remains the system of record.

The extension should limit itself to these behaviors:

- export a mirror
- list exported sessions
- resolve an artifact path to open
- generate a latest handoff

It should not depend on undocumented side effects or internal mirror structure beyond the documented contracts.

## Stable Commands For The Extension

### `codex-session-mirror --json`

Purpose:

- create or refresh the derived mirror
- get a machine-readable success payload for completion UX

Expected stdout shape:

```json
{
  "provider": "codex",
  "out_dir": "/abs/path/to/out",
  "session_count": 2,
  "rendered_count": 1,
  "reused_count": 1,
  "removed_count": 0,
  "redacted": false,
  "landing_relpath": "README.md",
  "reader_index_relpath": "index.html",
  "landing_path": "/abs/path/to/out/README.md",
  "reader_index_path": "/abs/path/to/out/index.html"
}
```

Stable fields:

- `provider`
- `out_dir`
- `session_count`
- `rendered_count`
- `reused_count`
- `removed_count`
- `redacted`
- `landing_relpath`
- `reader_index_relpath`
- `landing_path`
- `reader_index_path`

Exit behavior:

- exit code `0`
  - export succeeded and valid JSON was written
- non-zero
  - export failed and human-readable stderr explains why

### `codex-session-list --json`

Purpose:

- populate a session Quick Pick from the derived mirror

The stable contract for this command is documented separately in [list-json-contract.md](list-json-contract.md).

### `codex-session-open --print`

Purpose:

- resolve the exact artifact path that the extension should open

The extension may rely on these patterns:

- `codex-session-open --out-dir <...> --landing --print`
- `codex-session-open --out-dir <...> --landing --reader --print`
- `codex-session-open --out-dir <...> --latest --print`
- `codex-session-open --out-dir <...> --latest --reader --print`
- `codex-session-open --out-dir <...> --latest --handoff --print`
- `codex-session-open --out-dir <...> <session-id> --print`
- `codex-session-open --out-dir <...> <session-id> --reader --print`
- `codex-session-open --out-dir <...> <session-id> --handoff --print`

Behavior:

- stdout is a single absolute filesystem path
- exit code `0` means the path is ready to open
- non-zero means resolution failed and stderr explains why

### `codex-session-handoff --latest --print`

Purpose:

- generate the latest handoff bundle and return the Markdown path to open

Behavior:

- stdout is the absolute Markdown handoff path
- the command may create or refresh the paired `.json` artifact
- exit code `0` means the handoff was generated successfully

## Error Handling Expectations

The extension should surface raw CLI stderr with a short extension-specific hint instead of inventing a second error model.

At minimum, it should expect and handle:

- no exported sessions available
- invalid flag combination
- session selector not found
- session selector ambiguous
- missing mirror artifacts
- missing local environment or CLI entrypoint

## Scope Guardrails

The extension should not:

- read raw provider storage directly
- infer artifact paths by guessing file names
- parse provider sessions itself
- re-render mirror or handoff artifacts itself
- depend on fields outside the documented contracts unless they are explicitly promoted later
