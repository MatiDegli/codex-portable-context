"""Source and mirror path discovery helpers for the Python v2 core."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

from .contract import MirrorLayout


def default_codex_home() -> Path:
    """Return the default local Codex home directory."""

    raw_path = os.environ.get("CODEX_HOME")
    if raw_path:
        return Path(raw_path).expanduser()
    return Path.home() / ".codex"


def default_source_dir(codex_home: Path | None = None) -> Path:
    """Return the default Codex session source directory."""

    root = codex_home or default_codex_home()
    return root / "sessions"


def repo_root(start: Path | None = None) -> Path:
    """Locate the repository root for the current project."""

    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").exists() and (candidate / "README.md").exists():
            return candidate
    return current


def default_out_dir(start: Path | None = None) -> Path:
    """Resolve the default derived mirror directory."""

    root = repo_root(start)
    repo_out = root / "out"
    cwd_out = Path.cwd().resolve() / "out"
    if repo_out.is_dir():
        return repo_out
    if cwd_out.is_dir():
        return cwd_out
    return repo_out


def mirror_layout(out_dir: Path | None = None) -> MirrorLayout:
    """Create a mirror layout object for the chosen output directory."""

    return MirrorLayout((out_dir or default_out_dir()).resolve())


def iter_session_files(source_dir: Path) -> Iterator[Path]:
    """Yield session JSONL files in deterministic order."""

    yield from sorted(path for path in source_dir.rglob("*.jsonl") if path.is_file())


def source_relpath(file_path: Path, source_dir: Path) -> str:
    """Return a source-relative path string for one session file."""

    return file_path.resolve().relative_to(source_dir.resolve()).as_posix()
