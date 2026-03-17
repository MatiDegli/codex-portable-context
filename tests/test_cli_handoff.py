import json
from pathlib import Path

from codex_portable_context.cli.handoff import main
from codex_portable_context.core.mirror import MirrorExportConfig, export_mirror


def test_handoff_cli_generates_bundle_for_latest_session(tmp_path: Path, capsys) -> None:
    out_dir = build_fixture_mirror(tmp_path)

    exit_code = main(["--out-dir", str(out_dir), "--latest"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Handoff bundle written:" in captured.out
    assert (out_dir / "handoffs" / "session-5678.md").is_file()
    assert (out_dir / "handoffs" / "session-5678.json").is_file()

    payload = json.loads((out_dir / "handoffs" / "session-5678.json").read_text(encoding="utf-8"))
    assert payload["session_id"] == "session-5678"
    assert payload["source_availability"]["available"] is True
    assert (
        payload["session"]["last_substantive_user_request"]
        == "Please inspect Second Fixture Session."
    )
    assert payload["current_state"]["status"] == "in_progress"
    assert (
        payload["current_state"]["current_focus"]
        == "Please inspect Second Fixture Session."
    )
    assert (
        payload["current_state"]["next_recommended_action"]
        == (
            "Start a fresh local session and continue from this handoff's "
            "Current State and Open Loops."
        )
    )
    assert (
        payload["continuity_entry"]["primary_artifact_relpath"]
        == "handoffs/session-5678.md"
    )
    assert (
        payload["continuity_entry"]["machine_artifact_relpath"]
        == "handoffs/session-5678.json"
    )
    assert (
        payload["continuity_entry"]["transcript_fallback_relpath"]
        == "sessions/session-5678.md"
    )
    assert payload["continuity_entry"]["destination_workflow"]
    assert payload["artifacts"]["handoff_markdown_relpath"] == "handoffs/session-5678.md"
    assert payload["artifacts"]["handoff_json_relpath"] == "handoffs/session-5678.json"
    assert payload["artifacts"]["repo_root"] == str(repo_root())
    assert payload["artifacts"]["repo_branch"]
    assert payload["artifacts"]["repo_head_commit"]
    assert isinstance(payload["artifacts"]["repo_clean"], bool)
    assert payload["open_loops"]["pending_validation"] == "none"
    assert payload["open_loops"]["open_question"] == "none"
    assert payload["open_loops"]["unresolved_failure"] == "none"
    assert payload["open_loops"]["expected_next_command"] == "none"
    expected_risk = (
        "none"
        if payload["artifacts"]["repo_clean"] is True
        else "Repo has uncommitted changes."
    )
    assert payload["open_loops"]["operational_risk"] == expected_risk
    assert payload["recent_actions"]
    assert "ran ./scripts/validate-python-v2" in payload["recent_actions"]
    assert "updated README.md" in payload["recent_actions"]
    assert payload["recent_window"]
    assert any(
        "Please inspect Second Fixture Session." in item["text"]
        for item in payload["recent_window"]
    )

    markdown = (out_dir / "handoffs" / "session-5678.md").read_text(encoding="utf-8")
    assert "## Current State" in markdown
    assert "## Continuity Entry" in markdown
    assert "Last substantive user request" in markdown
    assert "## Recent Actions (normalized)" in markdown
    assert "### Destination Workflow" in markdown
    assert "## Open Loops / Risks" in markdown
    assert "Handoff JSON" in markdown
    assert "Recent Tool Activity (audit trail)" in markdown


def test_handoff_cli_prints_markdown_path_and_handles_missing_source(
    tmp_path: Path,
    capsys,
) -> None:
    out_dir = build_fixture_mirror(tmp_path)
    source_file = (
        tmp_path
        / ".codex"
        / "sessions"
        / "2026"
        / "03"
        / "16"
        / "rollout-2026-03-16T10-00-00-fixture-session-a.jsonl"
    )
    source_file.unlink()

    exit_code = main(["--out-dir", str(out_dir), "session-1234", "--print"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.strip() == str(out_dir / "handoffs" / "session-1234.md")

    payload = json.loads((out_dir / "handoffs" / "session-1234.json").read_text(encoding="utf-8"))
    assert payload["source_availability"]["available"] is False
    assert payload["recent_window"] == []
    assert payload["recent_actions"] == []
    assert (
        payload["open_loops"]["pending_validation"]
        == "Current changes have not been revalidated yet."
    )
    assert payload["open_loops"]["expected_next_command"] == "./scripts/validate-python-v2"
    assert (
        payload["open_loops"]["operational_risk"]
        == "Only derived mirror data is available locally."
    )


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
        cwd=str(repo_root()),
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
    cwd: str = "/home/tester/project",
) -> None:
    records = [
        {
            "timestamp": "2026-03-16T10:00:00Z",
            "type": "session_meta",
            "payload": {
                "id": session_id,
                "timestamp": "2026-03-16T09:59:00Z",
                "cwd": cwd,
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
                "type": "user_message",
                "message": (
                    "# Context from my IDE setup:\n\n"
                    "## Active file: README.md\n\n"
                    "## My request for Codex:\nProceed"
                ),
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
        {
            "timestamp": updated_at,
            "type": "response_item",
            "payload": {
                "type": "function_call",
                "name": "exec_command",
                "call_id": f"call-{session_id}",
                "arguments": json.dumps(
                    {"cmd": "./scripts/validate-python-v2", "workdir": "/home/tester/project"}
                ),
            },
        },
        {
            "timestamp": updated_at,
            "type": "response_item",
            "payload": {
                "type": "function_call_output",
                "call_id": f"call-{session_id}",
                "output": "All checks passed!\n",
            },
        },
        {
            "timestamp": updated_at,
            "type": "response_item",
            "payload": {
                "type": "function_call_output",
                "call_id": f"call-{session_id}",
                "output": "Success. Updated the following files:\nM README.md\n",
            },
        },
    ]
    path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]
