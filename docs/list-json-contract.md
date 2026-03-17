# `codex-session-list --json` Contract

## Purpose

`codex-session-list --json` is the preferred machine-readable listing surface for lightweight integrations such as a future VS Code extension.

It is intentionally read-only and mirror-only:

- it reads the derived mirror index
- it does not read raw `~/.codex`
- it does not generate new artifacts
- it does not mutate mirror state

## Output Shape

The command prints a single JSON array to stdout.

Each element is one filtered mirror entry.

Example:

```json
[
  {
    "session_id": "019cef3a-f82c-7790-af6d-eeeaca245196",
    "title": "Create Galaxy Book4 helper repo",
    "markdown_relpath": "sessions/019cef3a-f82c-7790-af6d-eeeaca245196.md",
    "reader_relpath": "reader/019cef3a-f82c-7790-af6d-eeeaca245196.html",
    "summary_line": "Role: You are a senior Linux tooling engineer...",
    "activity_line": "92 user messages, 484 assistant messages | 1221 tool calls, 1216 tool outputs | 189 notable events",
    "environment_line": "cwd: linux-fedora, source: vscode, originator: codex_vscode"
  }
]
```

## Stable Fields For Integrations

The following fields are the stable integration surface for `--json` consumers:

- `session_id`
- `title`
- `updated_at`
- `exported_at`
- `markdown_relpath`
- `metadata_relpath`
- `reader_relpath`
- `redacted`
- `summary`
- `redaction_report`
- `summary_line`
- `detail_line`
- `activity_line`
- `environment_line`
- `redaction_line`

These fields are expected to remain available unless the contract is explicitly revised.

## Field Expectations

### Identity And Basic Labeling

- `session_id`
  - string
  - full session identifier
- `title`
  - string
  - human-readable title from the derived mirror entry

### Artifact Paths

These are relative to the selected `--out-dir`.

- `markdown_relpath`
  - string
  - transcript Markdown path
- `metadata_relpath`
  - string
  - metadata JSON path
- `reader_relpath`
  - string
  - per-session reader HTML path

### Timing

- `updated_at`
  - string when known
  - preferred timestamp for recency-oriented displays
- `exported_at`
  - string when known
  - export generation timestamp

Integrations should treat timestamps as display or sort values, not as guaranteed timezone-normalized datetime objects.

### Summary And Display Helpers

- `summary`
  - object when available
  - raw derived summary object from the mirror entry
- `summary_line`
  - string
  - preview-oriented one-line helper
- `detail_line`
  - string
  - compact merged activity/environment helper
- `activity_line`
  - string
  - compact recent activity helper
- `environment_line`
  - string
  - compact environment helper

Consumers that only need Quick Pick labels should prefer:

- `title`
- `summary_line`
- `activity_line`

### Redaction Helpers

- `redacted`
  - boolean
  - whether the mirror entry came from a redacted export
- `redaction_report`
  - object
  - full redaction report from the mirror entry
- `redaction_line`
  - string
  - compact display helper such as `off` or a short totals line

## Explicitly Non-Stable Fields

Consumers should not depend on:

- field ordering
- pretty-print whitespace
- internal helper fields removed from the final payload
- every mirror-entry field not listed in the stable integration surface above

Additional fields may appear over time. Integrations should ignore unknown fields.

## Exit Behavior

- exit code `0`
  - one or more entries matched and valid JSON was written
- exit code `1`
  - no entries matched the current filters

On failure, human-readable error text is written to stderr.

## Integration Guidance

For a future VS Code extension or other lightweight UI:

- use `codex-session-list --json` for session selection
- use `codex-session-open --print` to resolve the exact artifact to open
- do not reconstruct artifact paths yourself beyond the documented relative path fields unless necessary

This keeps integrations thin and aligned with the Python CLI as the system of record.
