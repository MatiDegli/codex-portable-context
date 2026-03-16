"""Mirror index loading and entry helpers for the Python v2 core."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .contract import MirrorLayout
from .discovery import mirror_layout

MirrorEntry = dict[str, Any]


def require_index_path(out_dir: Path | None = None) -> Path:
    """Return the index path or raise if it is missing or empty."""

    layout = mirror_layout(out_dir)
    index_path = layout.index_path
    if not index_path.is_file():
        raise FileNotFoundError(
            f"Mirror index not found: {index_path}\n"
            "Run scripts/codex-session-mirror first, or pass --out-dir."
        )
    if index_path.stat().st_size == 0:
        raise FileNotFoundError(f"Mirror index is empty: {index_path}")
    return index_path


def require_landing_path(out_dir: Path | None = None) -> Path:
    """Return the landing path or raise if it is missing."""

    layout = mirror_layout(out_dir)
    landing_path = layout.landing_path
    if not landing_path.is_file():
        raise FileNotFoundError(
            f"Mirror landing not found: {landing_path}\n"
            "Run scripts/codex-session-mirror first, or pass --out-dir."
        )
    return landing_path


def require_reader_index_path(out_dir: Path | None = None) -> Path:
    """Return the reader landing path or raise if it is missing."""

    layout = mirror_layout(out_dir)
    reader_index_path = layout.reader_index_path
    if not reader_index_path.is_file():
        raise FileNotFoundError(
            f"Mirror reader index not found: {reader_index_path}\n"
            "Run codex-session-mirror first, or pass --out-dir."
        )
    return reader_index_path


def load_jsonl(path: Path) -> list[MirrorEntry]:
    """Load newline-delimited JSON objects from a file."""

    entries: list[MirrorEntry] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            entries.append(json.loads(stripped))
    return entries


def load_index(out_dir: Path | None = None) -> list[MirrorEntry]:
    """Load the derived mirror index from the chosen output directory."""

    return load_jsonl(require_index_path(out_dir))


def sort_timestamp(entry: MirrorEntry) -> str:
    """Return the best available sortable timestamp string for an entry."""

    for key in ("updated_at", "session_timestamp", "exported_at"):
        value = entry.get(key)
        if value:
            return str(value)
    return ""


def sort_entries(entries: Iterable[MirrorEntry]) -> list[MirrorEntry]:
    """Return entries sorted newest-first using the mirror contract order."""

    return sorted(
        entries,
        key=lambda entry: (sort_timestamp(entry), entry_session_id(entry)),
        reverse=True,
    )


def latest_entry(entries: Iterable[MirrorEntry]) -> MirrorEntry | None:
    """Return the latest mirror entry, if any."""

    ordered = sort_entries(entries)
    return ordered[0] if ordered else None


def entry_session_id(entry: MirrorEntry) -> str:
    """Return the session id for one entry."""

    session_id = entry.get("session_id")
    if not session_id:
        raise ValueError("Mirror entry is missing session_id.")
    return str(session_id)


def entry_title(entry: MirrorEntry) -> str:
    """Return the display title for one entry."""

    return str(entry.get("title") or f"Session {entry_session_id(entry)}")


def entry_brief_label(entry: MirrorEntry) -> str:
    """Return a short label like 'Title (019cef3a)'."""

    session_id = entry_session_id(entry)
    return f"{entry_title(entry)} ({session_id[:8]})"


def entry_relpath(entry: MirrorEntry, kind: str, layout: MirrorLayout | None = None) -> str:
    """Return the relative derived path for one entry."""

    active_layout = layout or mirror_layout()
    session_id = entry_session_id(entry)
    if kind == "markdown":
        return str(entry.get("markdown_relpath") or active_layout.markdown_relpath(session_id))
    if kind == "metadata":
        return str(entry.get("metadata_relpath") or active_layout.metadata_relpath(session_id))
    if kind == "reader":
        return str(entry.get("reader_relpath") or active_layout.reader_relpath(session_id))
    raise ValueError(f"Unknown mirror entry kind: {kind}")


def entry_path(entry: MirrorEntry, kind: str, out_dir: Path | None = None) -> Path:
    """Return the absolute derived path for one entry."""

    layout = mirror_layout(out_dir)
    return layout.out_dir / entry_relpath(entry, kind, layout=layout)
