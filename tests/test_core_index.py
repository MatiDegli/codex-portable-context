from pathlib import Path

from codex_portable_context.core.index import (
    entry_brief_label,
    entry_path,
    latest_entry,
    sort_entries,
)
from codex_portable_context.core.resolve import resolve_unique_entry


def test_sort_entries_prefers_newer_timestamp() -> None:
    entries = [
        {"session_id": "b-session", "title": "B", "updated_at": "2026-03-15T01:00:00Z"},
        {"session_id": "a-session", "title": "A", "updated_at": "2026-03-15T02:00:00Z"},
    ]

    ordered = sort_entries(entries)

    assert [entry["session_id"] for entry in ordered] == ["a-session", "b-session"]
    assert latest_entry(entries)["session_id"] == "a-session"


def test_resolve_unique_entry_accepts_unique_prefix() -> None:
    entries = [
        {"session_id": "019cef3a-f82c", "title": "One"},
        {"session_id": "abcd1234-ffff", "title": "Two"},
    ]

    resolved = resolve_unique_entry(entries, "019cef3a")

    assert resolved["title"] == "One"


def test_resolve_unique_entry_deduplicates_same_session_id() -> None:
    entries = [
        {
            "session_id": "019cef3a-f82c",
            "title": "Older Duplicate",
            "updated_at": "2026-03-15T01:00:00Z",
        },
        {
            "session_id": "019cef3a-f82c",
            "title": "Newer Duplicate",
            "updated_at": "2026-03-15T02:00:00Z",
        },
    ]

    resolved = resolve_unique_entry(entries, "019cef3a")

    assert resolved["title"] == "Newer Duplicate"


def test_resolve_unique_entry_keeps_distinct_prefixes_ambiguous() -> None:
    entries = [
        {"session_id": "019cef3a-f82c", "title": "One"},
        {"session_id": "019cef3a-abcd", "title": "Two"},
        {"session_id": "019cef3a-abcd", "title": "Two Duplicate"},
    ]

    try:
        resolve_unique_entry(entries, "019cef3a")
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected an ambiguous selector error.")

    assert "Ambiguous session selector: 019cef3a" in message
    assert message.count("019cef3a-f82c") == 1
    assert message.count("019cef3a-abcd") == 1


def test_entry_path_falls_back_to_contract_paths(tmp_path: Path) -> None:
    entry = {"session_id": "session-123", "title": "Example"}
    brief_label = entry_brief_label({"session_id": "session-12345678", "title": "Example"})

    assert entry_path(entry, "markdown", tmp_path) == tmp_path / "sessions" / "session-123.md"
    assert entry_path(entry, "metadata", tmp_path) == tmp_path / "metadata" / "session-123.json"
    assert brief_label == "Example (session-)"
