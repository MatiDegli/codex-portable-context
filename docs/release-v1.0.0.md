# v1.0.0 Draft

`codex-portable-context` v1.0.0 is the first usable release of the project.

It provides a local-first, read-only mirror of Codex session data so sessions are easier to review, recover, and transport without treating raw `~/.codex` as a sync format.

## Highlights

- read-only export from local Codex sessions into a derived mirror
- generated landing page at `out/README.md`
- per-session Markdown transcripts and metadata
- optional redacted export mode
- incremental export reuse and stale cleanup
- lightweight lookup helpers for list/open/latest flows
- optional Syncthing and `rsync` transport recipes for the derived mirror only

## Scope

This release is intentionally narrow:

- local-first
- read-only with respect to Codex source state
- no write-back into `~/.codex`
- no credential sync
- no daemon, backend, or embedded sync engine

## Platform Note

This release should be treated as Linux/Unix-oriented today.

It is a good fit for Linux and should also be reasonable inside WSL, but it is not being declared as Windows-native at `v1.0.0`.

## Non-Goals

- bidirectional sync
- resume engine
- search engine
- sync of raw `~/.codex`
- guaranteed DLP or secret detection

## Useful Commands

```bash
./scripts/codex-session-mirror
./scripts/codex-session-mirror --redact
./scripts/codex-session-list --latest --summary --details
./scripts/codex-session-open --landing --print
./scripts/codex-session-open --latest
```

## Validation Direction

The next phase is real-world validation, not immediate feature expansion.

Focus areas:

- which commands are used daily
- whether summaries are useful enough
- whether redaction is sufficient in practice
- whether the generated landing page is enough for navigation
- whether any small ergonomics fixes are still needed
