from pathlib import Path

from codex_portable_context.core.discovery import mirror_layout, source_relpath


def test_mirror_layout_uses_expected_filenames(tmp_path: Path) -> None:
    layout = mirror_layout(tmp_path)

    assert layout.index_path == tmp_path / "sessions-index.jsonl"
    assert layout.state_path == tmp_path / ".codex-session-mirror-state.jsonl"
    assert layout.metadata_path("abc") == tmp_path / "metadata" / "abc.json"
    assert layout.markdown_path("abc") == tmp_path / "sessions" / "abc.md"


def test_source_relpath_uses_posix_style(tmp_path: Path) -> None:
    source_dir = tmp_path / "sessions"
    session_file = source_dir / "2026" / "03" / "example.jsonl"
    session_file.parent.mkdir(parents=True)
    session_file.write_text("", encoding="utf-8")

    assert source_relpath(session_file, source_dir) == "2026/03/example.jsonl"
