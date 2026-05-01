import json
from pathlib import Path

from codex_portable_context.cli.handoff_audit import main
from codex_portable_context.core.mirror import MirrorExportConfig, export_mirror


def test_handoff_audit_cli_reports_memory_coverage(tmp_path: Path, capsys) -> None:
    out_dir = build_fixture_mirror(tmp_path)

    exit_code = main(["--out-dir", str(out_dir), "--limit", "2"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Audited 2 session(s): 1 with memory, 1 empty, 0 errored." in captured.out
    assert "Readiness:" in captured.out
    assert "READY" in captured.out
    assert "Rich Memory Session" in captured.out
    assert "Sparse Session" in captured.out
    assert "no_memory" in captured.out


def test_handoff_audit_cli_json_reports_counts_and_sources(
    tmp_path: Path,
    capsys,
) -> None:
    out_dir = build_fixture_mirror(tmp_path)

    exit_code = main(["--out-dir", str(out_dir), "--json", "session-rich"])
    captured = capsys.readouterr()

    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload["summary"]["audited"] == 1
    assert payload["summary"]["covered"] == 1
    assert payload["summary"]["readiness_counts"]
    assert payload["items"][0]["session_id"] == "session-rich"
    assert payload["items"][0]["readiness"] in {"ready", "review", "weak"}
    assert payload["items"][0]["quality_gates"] == payload["items"][0]["flags"]
    assert payload["items"][0]["counts"]["invariants"] >= 1
    assert "context_structural_memory" in payload["items"][0]["sources"]


def test_handoff_audit_cli_marks_sparse_prompt_weak(
    tmp_path: Path,
    capsys,
) -> None:
    out_dir = build_fixture_mirror(tmp_path)

    exit_code = main(["--out-dir", str(out_dir), "--json", "session-sparse"])
    captured = capsys.readouterr()

    assert exit_code == 0
    payload = json.loads(captured.out)
    item = payload["items"][0]
    assert item["readiness"] == "weak"
    assert "no_memory" in item["flags"]
    assert "low_confidence" in item["flags"]


def test_handoff_audit_cli_can_read_existing_handoffs_without_generating(
    tmp_path: Path,
    capsys,
) -> None:
    out_dir = build_fixture_mirror(tmp_path)
    assert main(["--out-dir", str(out_dir), "session-rich"]) == 0
    capsys.readouterr()

    exit_code = main(["--out-dir", str(out_dir), "--no-generate", "session-rich"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Audited 1 session(s): 1 with memory, 0 empty, 0 errored." in captured.out


def test_handoff_audit_cli_rejects_negative_limit(tmp_path: Path, capsys) -> None:
    out_dir = build_fixture_mirror(tmp_path)

    exit_code = main(["--out-dir", str(out_dir), "--limit", "-1"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "--limit must be zero or greater." in captured.err


def build_fixture_mirror(tmp_path: Path) -> Path:
    codex_home = tmp_path / ".codex"
    source_dir = codex_home / "sessions" / "2026" / "03" / "16"
    source_dir.mkdir(parents=True)

    write_session(
        source_dir / "rollout-2026-03-16T10-00-00-rich.jsonl",
        session_id="session-rich",
        updated_at="2026-03-16T10:00:00Z",
        thread_name="Rich Memory Session",
        developer_context=(
            "## Stable boundary\n\n"
            "- repo/workflow truth remains repo-owned\n"
            "- `workstation-public` explicitly does NOT own:\n"
            "  - provider/session/thread transport\n\n"
            "## Strategic decisions already made\n\n"
            "1. We explicitly chose a new repo for clean separation from day one.\n"
        ),
    )
    write_session(
        source_dir / "rollout-2026-03-16T10-05-00-sparse.jsonl",
        session_id="session-sparse",
        updated_at="2026-03-16T10:05:00Z",
        thread_name="Sparse Session",
        developer_context="Developer context without durable handoff memory markers.",
    )

    (codex_home / "session_index.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "id": "session-rich",
                        "thread_name": "Rich Memory Session",
                        "updated_at": "2026-03-16T10:00:00Z",
                    }
                ),
                json.dumps(
                    {
                        "id": "session-sparse",
                        "thread_name": "Sparse Session",
                        "updated_at": "2026-03-16T10:05:00Z",
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
    developer_context: str,
) -> None:
    records = [
        {
            "timestamp": "2026-03-16T09:59:00Z",
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
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "developer",
                "content": [{"type": "input_text", "text": developer_context}],
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
                "message": f"I inspected {thread_name}.",
                "phase": "final_answer",
            },
        },
    ]
    path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )
