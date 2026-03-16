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
