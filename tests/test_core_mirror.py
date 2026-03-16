import json
from pathlib import Path

from codex_portable_context.core.mirror import MirrorExportConfig, export_mirror


def test_export_mirror_writes_contract_files_and_reuses_state(tmp_path: Path) -> None:
    codex_home, session_path = write_fixture_session(tmp_path)
    out_dir = tmp_path / "out"

    first = export_mirror(
        MirrorExportConfig(
            codex_home=codex_home,
            source_dir=codex_home / "sessions",
            out_dir=out_dir,
        )
    )
    second = export_mirror(
        MirrorExportConfig(
            codex_home=codex_home,
            source_dir=codex_home / "sessions",
            out_dir=out_dir,
        )
    )

    session_id = "session-1234"
    metadata_path = out_dir / "metadata" / f"{session_id}.json"
    markdown_path = out_dir / "sessions" / f"{session_id}.md"
    reader_path = out_dir / "reader" / f"{session_id}.html"
    landing_path = out_dir / "README.md"
    reader_index_path = out_dir / "index.html"
    index_path = out_dir / "sessions-index.jsonl"
    state_path = out_dir / ".codex-session-mirror-state.jsonl"

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    index_entries = [
        json.loads(line)
        for line in index_path.read_text(encoding="utf-8").splitlines()
    ]

    assert first.rendered_count == 1
    assert first.reused_count == 0
    assert second.rendered_count == 0
    assert second.reused_count == 1
    assert first.session_count == 1
    assert metadata["session_id"] == session_id
    assert metadata["source_file"] == str(session_path.resolve())
    assert metadata["markdown_relpath"] == f"sessions/{session_id}.md"
    assert metadata["reader_relpath"] == f"reader/{session_id}.html"
    assert metadata["summary"]["preview"].startswith("Please mirror")
    assert metadata["redaction_report"]["enabled"] is False
    assert markdown_path.is_file()
    assert reader_path.is_file()
    assert landing_path.is_file()
    assert reader_index_path.is_file()
    assert state_path.is_file()
    assert index_entries[0]["session_id"] == session_id
    assert index_entries[0]["reader_relpath"] == f"reader/{session_id}.html"
    landing_text = landing_path.read_text(encoding="utf-8")
    reader_index_text = reader_index_path.read_text(encoding="utf-8")
    reader_text = reader_path.read_text(encoding="utf-8")
    assert f"[sessions/{session_id}.md](sessions/{session_id}.md)" in landing_text
    assert "[index.html](index.html)" in landing_text
    assert f'href="reader/{session_id}.html"' in reader_index_text
    assert 'href="handoffs/session-1234.md"' in reader_index_text
    assert "Standard export" in reader_index_text
    assert "../index.html" in reader_text
    assert "Jump to snapshot" in reader_text
    assert "Jump to handoff" in reader_text
    assert "Jump to raw metadata" in reader_text
    assert "Raw transcript Markdown" in reader_text
    assert "Handoff Markdown" in reader_text
    assert "codex-session-handoff session-" in reader_text
    assert "Please mirror /home/tester/project" in reader_text


def test_export_mirror_redacts_derived_output(tmp_path: Path) -> None:
    codex_home, _ = write_fixture_session(tmp_path)
    out_dir = tmp_path / "out-redacted"

    result = export_mirror(
        MirrorExportConfig(
            codex_home=codex_home,
            source_dir=codex_home / "sessions",
            out_dir=out_dir,
            redact=True,
        )
    )

    metadata_text = (out_dir / "metadata" / "session-1234.json").read_text(encoding="utf-8")
    markdown_text = (out_dir / "sessions" / "session-1234.md").read_text(encoding="utf-8")
    reader_text = (out_dir / "reader" / "session-1234.html").read_text(encoding="utf-8")
    metadata = json.loads(metadata_text)

    assert result.redacted is True
    assert "<redacted-home>" in metadata_text
    assert "<redacted-secret>" in metadata_text
    assert "C:\\Users\\tester\\project" not in metadata_text
    assert "<redacted-secret>" in markdown_text
    assert "Redacted export" in reader_text
    assert "&lt;redacted-home&gt;" in reader_text
    assert "&lt;redacted-secret&gt;" in reader_text
    assert metadata["redaction_report"]["enabled"] is True
    assert metadata["redaction_report"]["total_replacements"] > 0


def write_fixture_session(tmp_path: Path) -> tuple[Path, Path]:
    codex_home = tmp_path / ".codex"
    source_dir = codex_home / "sessions" / "2026" / "03" / "16"
    source_dir.mkdir(parents=True)
    session_path = source_dir / "rollout-2026-03-16T10-00-00-fixture-session.jsonl"

    records = [
        {
            "timestamp": "2026-03-16T10:00:00Z",
            "type": "session_meta",
            "payload": {
                "id": "session-1234",
                "timestamp": "2026-03-16T09:59:00Z",
                "cwd": "/home/tester/project",
                "originator": "codex_vscode",
                "cli_version": "0.200.0",
                "source": "vscode",
                "model_provider": "openai",
            },
        },
        {
            "timestamp": "2026-03-16T10:00:01Z",
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "developer",
                "content": [{"type": "input_text", "text": "Developer context for the session."}],
            },
        },
        {
            "timestamp": "2026-03-16T10:00:02Z",
            "type": "event_msg",
            "payload": {
                "type": "user_message",
                "message": (
                    "Please mirror /home/tester/project and C:\\Users\\tester\\project "
                    "and hide sk-1234567890abcdefghijklmnop."
                ),
            },
        },
        {
            "timestamp": "2026-03-16T10:00:03Z",
            "type": "event_msg",
            "payload": {
                "type": "agent_message",
                "message": "I will inspect the workspace and prepare the export.",
                "phase": "commentary",
            },
        },
        {
            "timestamp": "2026-03-16T10:00:04Z",
            "type": "response_item",
            "payload": {
                "type": "function_call",
                "name": "exec_command",
                "call_id": "call-1",
                "arguments": json.dumps({"cmd": "pwd", "workdir": "/home/tester/project"}),
            },
        },
        {
            "timestamp": "2026-03-16T10:00:05Z",
            "type": "response_item",
            "payload": {
                "type": "function_call_output",
                "call_id": "call-1",
                "output": "/home/tester/project\n",
            },
        },
        {
            "timestamp": "2026-03-16T10:00:06Z",
            "type": "event_msg",
            "payload": {
                "type": "task_complete",
                "turn_id": "turn-1",
                "status": "completed",
            },
        },
    ]
    session_path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )

    (codex_home / "session_index.jsonl").write_text(
        json.dumps(
            {
                "id": "session-1234",
                "thread_name": "Fixture Session",
                "updated_at": "2026-03-16T10:00:06Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return codex_home, session_path
