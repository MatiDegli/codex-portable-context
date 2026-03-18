"""Tests for the bounded read-only MCP bridge helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from codex_portable_context.core.mirror import MirrorExportConfig, export_mirror
from codex_portable_context.mcp.bridge import (
    get_latest_session_summary,
    session_artifacts_get,
    session_handoff_get,
    session_list,
)


def test_session_list_returns_filtered_sessions_with_absolute_paths(tmp_path: Path) -> None:
    out_dir = build_fixture_mirror(tmp_path)

    payload = session_list(out_dir=out_dir, id_filter="session-1234")

    assert payload["operation"] == "session_list"
    assert payload["out_dir"] == str(out_dir.resolve())
    assert payload["count"] == 1

    item = payload["sessions"][0]
    assert item["session_id"] == "session-1234"
    assert item["title"] == "Fixture Session"
    assert item["metadata_relpath"] == "metadata/session-1234.json"
    assert item["markdown_relpath"] == "sessions/session-1234.md"
    assert item["reader_relpath"] == "reader/session-1234.html"
    assert item["paths"]["metadata"] == str((out_dir / "metadata" / "session-1234.json").resolve())
    assert item["paths"]["session_markdown"] == str(
        (out_dir / "sessions" / "session-1234.md").resolve()
    )
    assert item["paths"]["reader"] == str((out_dir / "reader" / "session-1234.html").resolve())
    assert item["paths"]["handoff_markdown"] == str(
        (out_dir / "handoffs" / "session-1234.md").resolve()
    )


def test_get_latest_session_summary_returns_newest_entry_with_summary_fields(
    tmp_path: Path,
) -> None:
    out_dir = build_fixture_mirror(tmp_path)

    payload = get_latest_session_summary(out_dir=out_dir)

    assert payload["operation"] == "get_latest_session_summary"
    session = payload["session"]
    assert session["session_id"] == "session-5678"
    assert session["title"] == "Second Fixture Session"
    assert session["summary"]["preview"]
    assert session["paths"]["metadata"] == str(
        (out_dir / "metadata" / "session-5678.json").resolve()
    )


def test_session_artifacts_get_returns_expected_paths_for_unique_selector(tmp_path: Path) -> None:
    out_dir = build_fixture_mirror(tmp_path)

    payload = session_artifacts_get(out_dir=out_dir, selector="session-1234")

    assert payload["operation"] == "session_artifacts_get"
    artifact = payload["artifact"]
    assert artifact["session_id"] == "session-1234"
    assert artifact["paths"]["landing_path"] == str((out_dir / "README.md").resolve())
    assert artifact["paths"]["reader_index_path"] == str((out_dir / "index.html").resolve())
    assert artifact["paths"]["metadata_path"] == str(
        (out_dir / "metadata" / "session-1234.json").resolve()
    )
    assert artifact["paths"]["markdown_path"] == str(
        (out_dir / "sessions" / "session-1234.md").resolve()
    )
    assert artifact["paths"]["reader_path"] == str(
        (out_dir / "reader" / "session-1234.html").resolve()
    )
    assert artifact["relpaths"]["handoff_markdown_relpath"] == "handoffs/session-1234.md"
    assert artifact["relpaths"]["handoff_json_relpath"] == "handoffs/session-1234.json"


def test_session_artifacts_get_rejects_multiple_selection_modes(tmp_path: Path) -> None:
    out_dir = build_fixture_mirror(tmp_path)

    with pytest.raises(ValueError, match="exactly one selection mode"):
        session_artifacts_get(out_dir=out_dir, session_id="session-1234", latest=True)


def test_session_handoff_get_generates_handoff_and_returns_absolute_paths(tmp_path: Path) -> None:
    out_dir = build_fixture_mirror(tmp_path)

    payload = session_handoff_get(out_dir=out_dir, latest=True)

    assert payload["operation"] == "session_handoff_get"
    assert payload["out_dir"] == str(out_dir.resolve())
    assert payload["session_id"] == "session-5678"
    assert payload["artifact"]["session_id"] == "session-5678"
    assert payload["handoff"]["session_id"] == "session-5678"
    assert payload["handoff"]["artifacts"]["handoff_markdown_relpath"] == "handoffs/session-5678.md"
    assert payload["handoff"]["artifacts"]["handoff_json_relpath"] == "handoffs/session-5678.json"
    assert payload["paths"]["markdown"] == str((out_dir / "handoffs" / "session-5678.md").resolve())
    assert payload["paths"]["json"] == str((out_dir / "handoffs" / "session-5678.json").resolve())
    assert payload["paths"]["metadata"] == str(
        (out_dir / "metadata" / "session-5678.json").resolve()
    )
    assert payload["paths"]["session_markdown"] == str(
        (out_dir / "sessions" / "session-5678.md").resolve()
    )
    assert payload["paths"]["reader"] == str((out_dir / "reader" / "session-5678.html").resolve())
    assert (out_dir / "handoffs" / "session-5678.md").is_file()
    assert (out_dir / "handoffs" / "session-5678.json").is_file()


def test_session_handoff_get_supports_selector_lookup(tmp_path: Path) -> None:
    out_dir = build_fixture_mirror(tmp_path)

    payload = session_handoff_get(out_dir=out_dir, selector="session-1234")

    assert payload["session_id"] == "session-1234"
    assert payload["handoff"]["session_id"] == "session-1234"
    assert payload["paths"]["markdown"] == str((out_dir / "handoffs" / "session-1234.md").resolve())


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
        wrapped_request="Why is the IDE output empty?",
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
    wrapped_request: str = "Proceed",
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
                    "## Open tabs:\n"
                    "- README.md: README.md\n\n"
                    f"## My request for Codex:\n{wrapped_request}"
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
