import json
from pathlib import Path

from codex_portable_context.cli.mirror import main


def test_mirror_cli_prints_json_result(tmp_path: Path, capsys) -> None:
    codex_home = tmp_path / ".codex"
    source_dir = codex_home / "sessions" / "2026" / "03" / "16"
    source_dir.mkdir(parents=True)
    session_file = source_dir / "rollout-2026-03-16T10-00-00-fixture-session-a.jsonl"
    session_file.write_text(
        "\n".join(
            [
                json.dumps(
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
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-03-16T10:00:01Z",
                        "type": "event_msg",
                        "payload": {
                            "type": "user_message",
                            "message": "Please inspect Fixture Session.",
                        },
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (codex_home / "session_index.jsonl").write_text(
        json.dumps(
            {
                "id": "session-1234",
                "thread_name": "Fixture Session",
                "updated_at": "2026-03-16T10:00:01Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    out_dir = tmp_path / "out"
    exit_code = main(
        [
            "--codex-home",
            str(codex_home),
            "--source-dir",
            str(codex_home / "sessions"),
            "--out-dir",
            str(out_dir),
            "--json",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload == {
        "provider": "codex",
        "out_dir": str(out_dir.resolve()),
        "session_count": 1,
        "rendered_count": 1,
        "reused_count": 0,
        "removed_count": 0,
        "redacted": False,
        "landing_relpath": "README.md",
        "reader_index_relpath": "index.html",
        "landing_path": str((out_dir / "README.md").resolve()),
        "reader_index_path": str((out_dir / "index.html").resolve()),
    }
    assert captured.err == ""
