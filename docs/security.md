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

## Project Safety Invariants

- never require syncing credentials to get value from the project
- never require modifying Codex source files in place
- never assume concurrent multi-device writers are safe
- keep the mirror usable as a read-only context layer

## Redaction Direction

Redaction is not implemented yet, but the project should leave room for:

- path redaction
- hostname redaction
- tool output filtering
- selective export modes
