# Security

## Security Boundary

This project should default to a strict separation between:

- sensitive local Codex state
- raw local session files
- derived mirror artifacts

Only the third layer is a candidate for cross-device transport.

## Must Not Sync By Default

- `~/.codex/auth.json`
- `~/.codex/config.toml`
- `~/.codex/state_*.sqlite`
- `~/.codex/logs_*.sqlite`
- `*.sqlite-wal`
- `*.sqlite-shm`
- `~/.codex/tmp/`
- `~/.codex/shell_snapshots/`

## Practical Safety Rules

- treat `auth.json` like a password
- assume raw session files may contain sensitive prompts, outputs, paths, and command history
- prefer explicit export over blind directory replication
- prefer append-friendly derived artifacts over mutable shared state
- keep transport configuration separate from credential handling
- keep redaction best-effort and conservative

## Project Safety Invariants

- never require syncing credentials to get value from the project
- never require modifying Codex source files in place
- never assume concurrent multi-device writers are safe
- keep the mirror usable as a read-only context layer

## Redaction Direction

Redaction is now implemented as an optional export mode. It applies only to derived output and does not modify source session files.

Current conservative rules include:

- current username when confidently matched
- home-directory paths such as `/home/<user>/...`
- obvious local absolute home paths
- current hostname when confidently matched
- a small set of obvious token/secret patterns

Current placeholders:

- `<redacted-user>`
- `<redacted-home>`
- `<redacted-host>`
- `<redacted-secret>`

Redaction is best-effort, not a guaranteed DLP system. The goal is to reduce accidental leakage in portable mirror output without destroying large amounts of useful context.
