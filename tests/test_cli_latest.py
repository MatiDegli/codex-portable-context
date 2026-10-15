import json
from pathlib import Path

from codex_portable_context.cli.latest import main
from codex_portable_context.core.mirror import MirrorExportConfig, export_mirror


def test_latest_cli_prints_markdown_path(tmp_path: Path, capsys) -> None:
    out_dir = build_fixture_mirror(tmp_path)

    exit_code = main(["--out-dir", str(out_dir), "--print"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.strip() == str(out_dir / "sessions" / "session-5678.md")


def test_latest_cli_prints_metadata_path(tmp_path: Path, capsys) -> None:
    out_dir = build_fixture_mirror(tmp_path)

    exit_code = main(["--out-dir", str(out_dir), "--metadata", "--print"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.strip() == str(out_dir / "metadata" / "session-5678.json")


def test_latest_cli_prints_reader_path(tmp_path: Path, capsys) -> None:
    out_dir = build_fixture_mirror(tmp_path)

    exit_code = main(["--out-dir", str(out_dir), "--reader", "--print"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.strip() == str(out_dir / "reader" / "session-5678.html")


def test_latest_cli_prints_handoff_path(tmp_path: Path, capsys) -> None:
    out_dir = build_fixture_mirror(tmp_path)

    exit_code = main(["--out-dir", str(out_dir), "--handoff", "--print"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.strip() == str(out_dir / "handoffs" / "session-5678.md")


def build_fixture_mirror(tmp_path: Path) -> Path:
    codex_home = tmp_path / ".codex"
    source_dir = codex_home / "sessions" / "2026" / "03" / "16"
    source_dir.mkdir(parents=True)

    write_session(
        source_dir / "rollout-2026-03-16T10-00-00-fixture-session-a.jsonl",
        session_id="session-1234",
        updated_at="2026-03-16T10:00:06Z",
        thread_name="Fixture Session",
    )
    write_session(
        source_dir / "rollout-2026-03-16T10-05-00-fixture-session-b.jsonl",
        session_id="session-5678",
        updated_at="2026-03-16T10:05:06Z",
        thread_name="Second Fixture Session",
    )

    (codex_home / "session_index.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "id": "session-1234",
                        "thread_name": "Fixture Session",
                        "updated_at": "2026-03-16T10:00:06Z",
                    }
                ),
                json.dumps(
                    {
                        "id": "session-5678",
                        "thread_name": "Second Fixture Session",
                        "updated_at": "2026-03-16T10:05:06Z",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    out_dir = tmp_path / "out"
    export_mirror(
        MirrorExportConfig(
            codex_home=codex_home,
            source_dir=codex_home / "sessions",
            out_dir=out_dir,
        )
    )
    return out_dir


def write_session(
    path: Path,
    *,
    session_id: str,
    updated_at: str,
    thread_name: str,
) -> None:
    records = [
        {
            "timestamp": "2026-03-16T10:00:00Z",
            "type": "session_meta",
            "payload": {
                "id": session_id,
                "timestamp": "2026-03-16T09:59:00Z",
                "cwd": "/home/tester/project",
                "originator": "codex_vscode",
                "cli_version": "0.200.0",
                "source": "vscode",
                "model_provider": "openai",
            },
        },
        {
            "timestamp": updated_at,
            "type": "event_msg",
            "payload": {
                "type": "user_message",
                "message": f"Please inspect {thread_name}.",
            },
        },
        {
            "timestamp": updated_at,
            "type": "event_msg",
            "payload": {
                "type": "agent_message",
                "message": f"I will inspect {thread_name}.",
                "phase": "commentary",
            },
        },
    ]
    path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )
