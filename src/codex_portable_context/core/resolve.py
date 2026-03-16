"""Session resolution helpers for the Python v2 core."""

from __future__ import annotations

from typing import Iterable

from .index import MirrorEntry, entry_session_id, entry_title


def resolve_unique_entry(entries: Iterable[MirrorEntry], selector: str) -> MirrorEntry:
    """Resolve a unique entry by full session id or unique prefix."""

    entry_list = list(entries)
    exact_matches = [entry for entry in entry_list if entry_session_id(entry) == selector]
    if len(exact_matches) == 1:
        return exact_matches[0]

    prefix_matches = [entry for entry in entry_list if entry_session_id(entry).startswith(selector)]
    if len(prefix_matches) == 1:
        return prefix_matches[0]

    if not prefix_matches:
        raise ValueError(f"No exported session matched selector: {selector}")

    lines = "\n".join(
        f"- {entry_session_id(entry)}  {entry_title(entry)}" for entry in prefix_matches
    )
    raise ValueError(f"Ambiguous session selector: {selector}\n{lines}")
