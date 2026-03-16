# Python v2 Conventions

## Purpose

This document defines the working conventions for the Python v2 migration.

The goal is to keep the project understandable for a solo developer while preserving the v1 product behavior and the frozen mirror contract.

## Core Principles

- keep v1 stable while building v2
- prefer one reusable Python core over command-by-command duplication
- preserve the mirror contract unless a change is explicitly justified
- stay local-first and read-only with respect to Codex source state
- prefer Python stdlib first
- prefer clear cross-platform behavior over clever platform-specific shortcuts

## Architecture Rules

- put reusable logic under `src/codex_portable_context/core/`
- keep CLI entry points thin under `src/codex_portable_context/cli/`
- do not let CLI modules become the real implementation layer
- do not port Bash scripts mechanically one by one without shared abstractions

## Compatibility Rules

- treat v1 Bash output as the compatibility baseline
- follow [mirror-contract.md](mirror-contract.md) before changing derived output
- preserve file roles:
  - `README.md`
  - `sessions-index.jsonl`
  - `metadata/<session-id>.json`
  - `sessions/<session-id>.md`
  - `.codex-session-mirror-state.jsonl`
- prefer additive optional fields over renaming or removing stable fields

## Cross-OS Rules

- use `pathlib` for path handling
- explicitly support both Unix-style and Windows-style path redaction
- avoid hard-coding Linux-only path assumptions in new Python logic
- use Python stdlib for opener behavior and platform detection where possible
- tolerate line ending differences across operating systems

## Dependency Rules

- start with stdlib only unless a dependency clearly earns its place
- do not add libraries just to mimic shell tooling
- add third-party tooling only when it improves safety or maintainability enough to justify the extra surface area

## CLI Rules

- keep current CLI semantics conceptually compatible where reasonable
- preserve the same main command roles:
  - mirror
  - list
  - open
  - latest
- keep help output concise and example-driven

## Testing and Validation Rules

- validate Python output against the frozen mirror contract
- compare Python-generated mirror output to v1 output during the migration
- test behavior on Linux and Windows deliberately
- focus first on correctness and compatibility, then on cleanup

## Bash Policy

- do not remove working v1 Bash scripts yet
- do not keep expanding Bash as the long-term core
- once Python reaches parity, decide whether Bash remains as thin wrappers or is retired with a documented migration path
