import json
from pathlib import Path

from codex_portable_context.cli.list import main
from codex_portable_context.core.mirror import MirrorExportConfig, export_mirror


def test_list_cli_json_and_filtering(tmp_path: Path, capsys) -> None:
    out_dir = build_fixture_mirror(tmp_path)

    exit_code = main(["--out-dir", str(out_dir), "--id", "session-1234", "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert len(payload) == 1
    assert payload[0]["session_id"] == "session-1234"


def test_list_cli_human_output_with_details_and_redaction(tmp_path: Path, capsys) -> None:
    out_dir = build_fixture_mirror(tmp_path, redact=True)

    exit_code = main(
        [
            "--out-dir",
            str(out_dir),
            "--latest",
            "--summary",
            "--details",
            "--redaction",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "SESSION ID" in captured.out
    assert "Fixture Session" in captured.out
    assert "preview" in captured.out
    assert "activity" in captured.out
    assert "environment" in captured.out
    assert "redaction" in captured.out


def test_list_cli_returns_error_when_no_sessions_match(tmp_path: Path, capsys) -> None:
    out_dir = build_fixture_mirror(tmp_path)

    exit_code = main(["--out-dir", str(out_dir), "--title", "missing"])

    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "No exported sessions matched the current filters." in captured.err


def build_fixture_mirror(tmp_path: Path, *, redact: bool = False) -> Path:
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
                    "Please mirror /home/tester/project and hide "
                    "sk-1234567890abcdefghijklmnop."
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

    out_dir = tmp_path / ("out-redacted" if redact else "out")
    export_mirror(
        MirrorExportConfig(
            codex_home=codex_home,
            source_dir=codex_home / "sessions",
            out_dir=out_dir,
            redact=redact,
        )
    )
    return out_dir
