import json
from pathlib import Path

from codex_portable_context.cli.open import main
from codex_portable_context.core.mirror import MirrorExportConfig, export_mirror


def test_open_cli_prints_landing_and_metadata_paths(tmp_path: Path, capsys) -> None:
    out_dir = build_fixture_mirror(tmp_path)

    landing_code = main(["--out-dir", str(out_dir), "--landing", "--print"])
    landing_output = capsys.readouterr()
    metadata_code = main(["--out-dir", str(out_dir), "session-1234", "--metadata", "--print"])
    metadata_output = capsys.readouterr()

    assert landing_code == 0
    assert metadata_code == 0
    assert landing_output.out.strip() == str(out_dir / "README.md")
    assert metadata_output.out.strip() == str(out_dir / "metadata" / "session-1234.json")


def test_open_cli_prints_reader_paths(tmp_path: Path, capsys) -> None:
    out_dir = build_fixture_mirror(tmp_path)

    landing_code = main(["--out-dir", str(out_dir), "--landing", "--reader", "--print"])
    landing_output = capsys.readouterr()
    reader_code = main(["--out-dir", str(out_dir), "session-1234", "--reader", "--print"])
    reader_output = capsys.readouterr()

    assert landing_code == 0
    assert reader_code == 0
    assert landing_output.out.strip() == str(out_dir / "index.html")
    assert reader_output.out.strip() == str(out_dir / "reader" / "session-1234.html")


def test_open_cli_latest_prints_transcript_path(tmp_path: Path, capsys) -> None:
    out_dir = build_fixture_mirror(tmp_path)

    exit_code = main(["--out-dir", str(out_dir), "--latest", "--print"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.strip() == str(out_dir / "sessions" / "session-1234.md")


def test_open_cli_reports_ambiguous_selector(tmp_path: Path, capsys) -> None:
    out_dir = build_fixture_mirror(tmp_path, extra_session=True)

    exit_code = main(["--out-dir", str(out_dir), "session", "--print"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Ambiguous session selector: session" in captured.err
    assert "session-1234" in captured.err
    assert "session-5678" in captured.err


def test_open_cli_rejects_invalid_flag_combo(tmp_path: Path, capsys) -> None:
    out_dir = build_fixture_mirror(tmp_path)

    exit_code = main(["--out-dir", str(out_dir), "--landing", "--metadata"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "--metadata cannot be combined with --landing." in captured.err


def test_open_cli_rejects_reader_and_metadata_combo(tmp_path: Path, capsys) -> None:
    out_dir = build_fixture_mirror(tmp_path)

    exit_code = main(["--out-dir", str(out_dir), "session-1234", "--reader", "--metadata"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Use only one of --metadata or --reader." in captured.err


def build_fixture_mirror(
    tmp_path: Path,
    *,
    extra_session: bool = False,
) -> Path:
    codex_home = tmp_path / ".codex"
    source_dir = codex_home / "sessions" / "2026" / "03" / "16"
    source_dir.mkdir(parents=True)
    write_session(
        source_dir / "rollout-2026-03-16T10-00-00-fixture-session-a.jsonl",
        session_id="session-1234",
        updated_at="2026-03-16T10:00:06Z",
        thread_name="Fixture Session",
    )
    if extra_session:
        write_session(
            source_dir / "rollout-2026-03-16T10-05-00-fixture-session-b.jsonl",
            session_id="session-5678",
            updated_at="2026-03-16T10:05:06Z",
            thread_name="Second Fixture Session",
        )

    index_lines = [
        json.dumps(
            {
                "id": "session-1234",
                "thread_name": "Fixture Session",
                "updated_at": "2026-03-16T10:00:06Z",
            }
        )
    ]
    if extra_session:
        index_lines.append(
            json.dumps(
                {
                    "id": "session-5678",
                    "thread_name": "Second Fixture Session",
                    "updated_at": "2026-03-16T10:05:06Z",
                }
            )
        )
    (codex_home / "session_index.jsonl").write_text("\n".join(index_lines) + "\n", encoding="utf-8")

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
            "timestamp": "2026-03-16T10:00:01Z",
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "developer",
                "content": [
                    {
                        "type": "input_text",
                        "text": f"Developer context for {thread_name}.",
                    }
                ],
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
