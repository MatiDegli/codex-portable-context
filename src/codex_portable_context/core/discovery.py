"""Source and mirror path discovery helpers for the Python v2 core."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from codex_portable_context.providers import get_provider_adapter

from .contract import MirrorLayout
from .source_paths import source_relpath as _source_relpath


def default_codex_home() -> Path:
    """Return the default local Codex home directory."""

    return get_provider_adapter("codex").default_home_dir()


def default_source_dir(codex_home: Path | None = None) -> Path:
    """Return the default Codex session source directory."""

    root = codex_home or default_codex_home()
    return get_provider_adapter("codex").default_source_dir(root)


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

    yield from sorted(
        path
        for path in source_dir.rglob("rollout-*.jsonl")
        if path.is_file()
    )


def source_relpath(file_path: Path, source_dir: Path) -> str:
    """Return a source-relative path string for one session file."""

    return _source_relpath(file_path, source_dir)
