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
