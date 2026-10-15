from pathlib import Path

from codex_portable_context.core.discovery import iter_session_files, mirror_layout, source_relpath


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


def test_iter_session_files_matches_rollout_baseline(tmp_path: Path) -> None:
    source_dir = tmp_path / "sessions"
    source_dir.mkdir(parents=True)
    skipped = source_dir / "fixture.jsonl"
    included = source_dir / "rollout-2026-03-16T10-00-00-session.jsonl"
    skipped.write_text("", encoding="utf-8")
    included.write_text("", encoding="utf-8")

    assert [path.name for path in iter_session_files(source_dir)] == [included.name]
