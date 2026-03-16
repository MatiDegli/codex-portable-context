# Python v2 Architecture Brief

## Decision

`codex-portable-context` v2 should move the implementation core from Bash to Python.

This is an implementation shift, not a product thesis shift.

The product thesis remains:

- local-first
- read-only with respect to Codex source state
- no raw sync of `~/.codex`
- no write-back into Codex state
- no credential sync
- no daemon or service
- no backend requirement
- derived mirror remains the core output

## Why Python v2 Is the Correct Move

The v1 Bash implementation is a strong Linux/Unix baseline, but it is not a strong long-term base for:

- Windows native support
- Linux native support with the same conceptual UX
- real cross-OS portability
- future compatibility work that needs one shared core

The current shell stack depends on Unix-oriented tools such as:

- `bash`
- `jq`
- `perl`
- `stat`
- `fold`
- `less`
- `xdg-open`

Trying to patch Windows support onto that stack would create a fragile split implementation. A small Python core is the more boring and portable foundation.

## Freeze v1 First

v1 should be treated as the baseline reference implementation.

Implications:

- do not destabilize working v1 scripts during the migration
- use v1 output as the compatibility reference
- preserve current CLI semantics conceptually where reasonable
- keep Bash scripts available until Python replacements are ready

## v2 Design Principles

1. Reuse one Python core, not four separate rewrites.
2. Preserve mirror compatibility unless a format break is strongly justified.
3. Keep the CLIs thin.
4. Use Python stdlib where possible.
5. Prefer cross-platform boring choices over clever platform-specific tricks.

## Python Runtime Policy

Python runtime policy for v2:

- baseline development target: Python 3.13
- supported target: Python 3.13+
- host system Python may be newer and that is acceptable
- contributors should use an explicit project environment instead of relying on whatever host Python is first in `PATH`

Implications:

- v2 should be written and validated with Python 3.13 as the main baseline
- compatibility with Python 3.14+ is desirable as long as the code remains compatible
- the project should not assume that the host operating system must use Python 3.13 as its system Python
- packaging and docs should express `>=3.13`, not `==3.13`

## Proposed Package Layout

```text
src/
└── codex_portable_context/
    ├── __init__.py
    ├── core/
    │   ├── __init__.py
    │   ├── contract.py
    │   ├── discovery.py
    │   ├── parsing.py
    │   ├── mirror.py
    │   ├── summaries.py
    │   ├── redaction.py
    │   ├── state.py
    │   ├── index.py
    │   ├── resolve.py
    │   ├── markdown.py
    │   └── opening.py
    └── cli/
        ├── __init__.py
        ├── mirror.py
        ├── list.py
        ├── open.py
        └── latest.py
```

## Core Responsibilities

The Python core should own:

- source session discovery
- source parsing
- derived mirror generation
- summary derivation
- redaction
- incremental state handling
- index loading
- session resolution helpers
- cross-platform open-path helpers

The CLI layer should own:

- argument parsing
- validation of CLI combinations
- presentation of human-readable output
- process exit codes

## Command Mapping

Current command to future Python CLI mapping:

- `scripts/codex-session-mirror`
  -> `python -m codex_portable_context.cli.mirror`
- `scripts/codex-session-list`
  -> `python -m codex_portable_context.cli.list`
- `scripts/codex-session-open`
  -> `python -m codex_portable_context.cli.open`
- `scripts/codex-session-latest`
  -> `python -m codex_portable_context.cli.latest`

Preferred semantic continuity:

- keep the same conceptual command names
- keep the same main flags where reasonable
- keep the same mirror layout and helper expectations

## Cross-OS Concerns

Python v2 should explicitly handle:

- Linux home directory detection
- Windows home directory detection
- Unix-style and Windows-style path redaction
- path normalization without breaking exported relative paths
- line ending tolerance
- file metadata and timestamp handling across OS
- opener behavior across platforms

Suggested stdlib-first approach:

- `pathlib`
- `json`
- `hashlib`
- `datetime`
- `re`
- `argparse`
- `os`
- `sys`
- `subprocess`
- `platform`
- `tempfile`
- `shutil`

Cross-platform opener direction:

- Windows: `os.startfile()` where available
- macOS: `open`
- Linux: `xdg-open`
- fallback: print path or open with `$EDITOR`

## Migration Phases

### Phase 0: Freeze and document v1 baseline

- treat current Bash implementation as the behavioral reference
- freeze the mirror contract
- avoid feature expansion during the migration setup

### Phase 1: Define mirror/output contract

- document stable required fields
- document optional fields
- document state-file expectations
- define compatibility rules for Python v2

### Phase 2: Build reusable Python core

- create package skeleton
- design internal modules around responsibilities, not scripts
- add parsing, summary, redaction, and state abstractions

Initial Phase 2 baseline now exists in the repo with shared modules for:

- mirror contract constants
- source and output discovery
- index loading
- session resolution
- cross-platform opening helpers

### Phase 3: Port `codex-session-mirror`

- highest-value command
- use it to prove cross-OS mirror generation
- compare Python output to v1 output as the compatibility baseline

Current status:

- an initial Python exporter now exists at `python -m codex_portable_context.cli.mirror`
- it uses shared core modules for parsing, summaries, redaction, state handling, markdown rendering, landing generation, and mirror writing
- the Bash exporter remains the frozen v1 reference while compatibility is validated

### Phase 4: Port `codex-session-list`

- move helper logic onto the shared Python index/summary layer
- preserve current CLI semantics where reasonable

Current status:

- an initial Python list CLI now exists at `python -m codex_portable_context.cli.list`
- it reads only the derived mirror index
- it supports the current reading-oriented flags: `--limit`, `--latest`, `--title`, `--id`, `--summary`, `--details`, `--redaction`, and `--json`

### Phase 5: Port `codex-session-open`

- move session resolution and opener behavior into shared Python logic
- handle Windows and Linux open behavior deliberately

Current status:

- an initial Python open CLI now exists at `python -m codex_portable_context.cli.open`
- it supports `--landing`, `--latest`, `--metadata`, and `--print`
- it resolves only derived mirror files and does not touch raw `~/.codex`

### Phase 6: Port `codex-session-latest`

- keep it thin on top of the shared resolver/index layer

Current status:

- an initial Python latest CLI now exists at `python -m codex_portable_context.cli.latest`
- it stays intentionally thin by delegating to the Python open CLI with `--latest`
- it supports `--out-dir`, `--metadata`, and `--print`

### Phase 7: Decide Bash wrapper policy

- either keep Bash scripts as thin compatibility wrappers
- or deprecate them after the Python CLIs are stable and documented

## Bash Wrapper Recommendation

Recommended path:

- keep Bash scripts temporarily as legacy wrappers during the migration
- once Python CLIs are stable, decide between:
  - thin wrappers that invoke Python
  - or retirement with clear migration notes

Current recommendation:

- do not remove Bash now
- do not expand Bash meaningfully further
- plan to deprecate Bash after Python v2 reaches parity

## Minimal Repo Preparation

Minimal repo restructuring is appropriate now:

- add `src/codex_portable_context/`
- add empty package markers for `core` and `cli`
- keep `scripts/` intact as the v1 surface
- keep docs explicit about v1 baseline and v2 migration

This makes the destination architecture concrete without starting the rewrite prematurely.

Recommended contributor setup:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
```

If a host ships a newer default Python, contributors should still create an explicit project environment rather than depending on the host default implicitly.

## Validation Strategy for the Python Port

During v2, compare Python behavior against the frozen v1 contract:

- same output layout
- same required JSON fields
- same path roles
- same summary/redaction object shapes where practical
- same helper-facing index expectations

The goal is compatibility first, cleanup second.

## Recommended Next Step

Do not start by porting all commands.

The next practical step should be:

1. keep v1 frozen
2. begin Phase 2 by creating the Python core skeleton
3. implement only the first shared internal modules needed for mirror generation
4. port `codex-session-mirror` first and validate it against the frozen contract
