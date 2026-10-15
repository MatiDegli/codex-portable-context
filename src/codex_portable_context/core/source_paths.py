"""Provider-neutral source path helpers."""

from __future__ import annotations

from pathlib import Path


def source_relpath(file_path: Path, source_dir: Path) -> str:
    """Return a source-relative path string for one session file."""

    return file_path.resolve().relative_to(source_dir.resolve()).as_posix()
