# Phase 7 Parity Status

## Scope

Phase 7 kept the Bash implementation in place as the explicit v1 reference while reviewing the Python CLIs for:

- parity with important Bash semantics
- cross-OS hardening for Linux and Windows native usage
- obvious output and behavior drift

## Parity Findings

### Fixed in this phase

- Python mirror discovery now matches the Bash exporter by reading only `rollout-*.jsonl`.
- Python list output now wraps labeled detail lines without relying on Unix `fold`.
- Windows path redaction is now covered by tests with `C:\Users\...`-style content.
- Windows open behavior now calls `os.startfile(str(path))` explicitly.

### Intentionally still different

- Python transcript and landing prose are not expected to be byte-for-byte identical to Bash output.
- Python is now the active path, while Bash remains the frozen behavioral reference for historical comparison.

Later follow-up:

- the Python-first ergonomics pass switched help output to the installed command names such as `codex-session-mirror`, while keeping `python -m ...` available as a fallback invocation path

### Current parity confidence

- `list --json` matches Bash behavior on the same derived mirror.
- `open --print` and `latest --print` match Bash path resolution semantics on the same derived mirror.
- Python and Bash mirror exports align on the stable metadata fields that matter for the contract.

## Outcome

This parity review was strong enough to support the Phase 8 transition:

- Python is now the primary implementation path
- Bash can move to thin compatibility wrappers
- the Bash code no longer needs to remain a second full implementation core
- the last full Bash implementation can stay available historically through the `bash-v1-baseline` git tag

## Remaining Pre-Wrapper Limitations

- Python and Bash transcript prose may still differ in formatting details.
- The Python mirror exporter should keep being compared against the frozen contract as more edge cases are found.
- Bash is still the safest immediate reference for diagnosing regression reports during the migration window.
