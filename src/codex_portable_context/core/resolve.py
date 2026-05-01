"""Session resolution helpers for the Python v2 core."""

from __future__ import annotations

from collections.abc import Iterable

from .index import MirrorEntry, entry_session_id, entry_title, sort_entries


def resolve_unique_entry(entries: Iterable[MirrorEntry], selector: str) -> MirrorEntry:
    """Resolve a unique entry by full session id or unique prefix."""

    entry_list = list(entries)
    exact_matches = [entry for entry in entry_list if entry_session_id(entry) == selector]
    exact_unique = _unique_by_session_id(exact_matches)
    if len(exact_unique) == 1:
        return exact_unique[0]

    prefix_matches = [entry for entry in entry_list if entry_session_id(entry).startswith(selector)]
    prefix_unique = _unique_by_session_id(prefix_matches)
    if len(prefix_unique) == 1:
        return prefix_unique[0]

    if not prefix_unique:
        raise ValueError(f"No exported session matched selector: {selector}")

    lines = "\n".join(
        f"- {entry_session_id(entry)}  {entry_title(entry)}" for entry in prefix_unique
    )
    raise ValueError(f"Ambiguous session selector: {selector}\n{lines}")


def _unique_by_session_id(entries: Iterable[MirrorEntry]) -> list[MirrorEntry]:
    unique: dict[str, MirrorEntry] = {}
    for entry in sort_entries(entries):
        unique.setdefault(entry_session_id(entry), entry)
    return list(unique.values())
