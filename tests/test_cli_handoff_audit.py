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
    assert "Source contract: pass=2, review=0, fail=0, error=0." in captured.out
    assert "Purpose:" in captured.out
    assert "READY" in captured.out
    assert "PURPOSE" in captured.out
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
    assert payload["summary"]["purpose_counts"]
    assert payload["items"][0]["session_id"] == "session-rich"
    assert payload["items"][0]["readiness"] in {"ready", "review", "weak"}
    assert payload["items"][0]["session_purpose"] == "substantive_work"
    assert payload["items"][0]["quality_gates"] == payload["items"][0]["flags"]
    assert payload["items"][0]["counts"]["invariants"] >= 1
    assert "context_structural_memory" in payload["items"][0]["sources"]
    assert payload["items"][0]["prompt_compliance"]["status"] == "pass"
    assert payload["items"][0]["source_contract_compliance"]["status"] == "pass"
    assert payload["items"][0]["source_contract_compliance"]["checks"][
        "section_sources_complete"
    ] is True
    assert payload["summary"]["prompt_compliance_counts"]["pass"] == 1
    assert payload["summary"]["source_contract_counts"]["pass"] == 1


def test_handoff_audit_cli_marks_sparse_prompt_minimal_expected(
    tmp_path: Path,
    capsys,
) -> None:
    out_dir = build_fixture_mirror(tmp_path)

    exit_code = main(["--out-dir", str(out_dir), "--json", "session-sparse"])
    captured = capsys.readouterr()

    assert exit_code == 0
    payload = json.loads(captured.out)
    item = payload["items"][0]
    assert item["session_purpose"] == "empty_or_noise"
    assert item["readiness"] == "minimal_expected"
    assert "no_memory" in item["flags"]
    assert "low_confidence" in item["flags"]


def test_handoff_audit_cli_marks_bootstrap_without_memory_minimal_expected(
    tmp_path: Path,
    capsys,
) -> None:
    out_dir = build_fixture_mirror(tmp_path, include_bootstrap=True)

    exit_code = main(["--out-dir", str(out_dir), "--json", "session-bootstrap"])
    captured = capsys.readouterr()

    assert exit_code == 0
    payload = json.loads(captured.out)
    item = payload["items"][0]
    assert item["session_purpose"] == "bootstrap_or_ack"
    assert item["readiness"] == "minimal_expected"
    assert "no_memory" in item["flags"]
    assert payload["summary"]["readiness_counts"]["minimal_expected"] == 1
    assert payload["summary"]["purpose_counts"]["bootstrap_or_ack"] == 1


def test_handoff_audit_cli_marks_active_unanswered_session_for_review(
    tmp_path: Path,
    capsys,
) -> None:
    out_dir = build_fixture_mirror(tmp_path, include_active=True)

    exit_code = main(["--out-dir", str(out_dir), "--json", "session-active"])
    captured = capsys.readouterr()

    assert exit_code == 0
    payload = json.loads(captured.out)
    item = payload["items"][0]
    assert item["session_purpose"] == "active_in_progress"
    assert item["readiness"] == "review"
    assert "no_memory" in item["flags"]
    assert payload["summary"]["readiness_counts"]["review"] == 1
    assert payload["summary"]["purpose_counts"]["active_in_progress"] == 1


def test_handoff_audit_cli_marks_active_review_session_for_review(
    tmp_path: Path,
    capsys,
) -> None:
    out_dir = build_fixture_mirror(
        tmp_path,
        include_active=True,
        active_thread_name="Active Review Session",
    )

    exit_code = main(["--out-dir", str(out_dir), "--json", "session-active"])
    captured = capsys.readouterr()

    assert exit_code == 0
    payload = json.loads(captured.out)
    item = payload["items"][0]
    assert item["session_purpose"] == "active_in_progress"
    assert item["readiness"] == "review"
    assert "no_memory" in item["flags"]


def test_handoff_audit_cli_flags_prompt_without_required_format(
    tmp_path: Path,
    capsys,
) -> None:
    out_dir = build_fixture_mirror(tmp_path)
    assert main(["--out-dir", str(out_dir), "session-rich"]) == 0
    capsys.readouterr()
    handoff_json = out_dir / "handoffs" / "session-rich.json"
    mutate_restart_prompt(
        handoff_json,
        lambda text: text.replace("Required first response format:", "Response format:"),
    )

    exit_code = main(["--out-dir", str(out_dir), "--no-generate", "--json", "session-rich"])
    captured = capsys.readouterr()

    assert exit_code == 0
    payload = json.loads(captured.out)
    item = payload["items"][0]
    assert item["prompt_compliance"]["status"] == "review"
    assert "prompt_missing_required_first_response_format" in item["flags"]
    assert item["readiness"] == "review"
    assert payload["summary"]["prompt_compliance_counts"]["review"] == 1


def test_handoff_audit_cli_flags_unsafe_first_action(
    tmp_path: Path,
    capsys,
) -> None:
    out_dir = build_fixture_mirror(tmp_path)
    assert main(["--out-dir", str(out_dir), "session-rich"]) == 0
    capsys.readouterr()
    handoff_json = out_dir / "handoffs" / "session-rich.json"
    mutate_restart_prompt(
        handoff_json,
        lambda text: replace_first_action(
            text,
            "First action: inspect files and implement the next change.",
        ),
    )

    exit_code = main(["--out-dir", str(out_dir), "--no-generate", "--json", "session-rich"])
    captured = capsys.readouterr()

    assert exit_code == 0
    payload = json.loads(captured.out)
    item = payload["items"][0]
    assert item["prompt_compliance"]["status"] == "fail"
    assert "prompt_unsafe_first_action" in item["flags"]
    assert "prompt_first_action_missing_confirmation_wait" in item["flags"]
    assert item["readiness"] == "weak"
    assert payload["summary"]["prompt_compliance_counts"]["fail"] == 1


def test_handoff_audit_cli_writes_manual_e2e_manifest(
    tmp_path: Path,
    capsys,
) -> None:
    out_dir = build_fixture_mirror(tmp_path)
    manifest_path = tmp_path / "e2e" / "restart-prompts.json"

    exit_code = main(
        [
            "--out-dir",
            str(out_dir),
            "--write-e2e-manifest",
            str(manifest_path),
            "session-rich",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert f"E2E manifest written: {manifest_path}" in captured.err
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["kind"] == "restart_prompt_e2e_manifest"
    assert manifest["schema_version"] == 1
    assert manifest["mode"] == "manual_only"
    assert manifest["result_status_values"] == ["not_run", "pass", "fail", "blocked"]
    assert manifest["safety"]["launches_agents"] is False
    assert manifest["safety"]["sends_messages"] is False
    assert manifest["summary"]["cases"] == 1
    assert manifest["summary"]["prompt_compliance_counts"]["pass"] == 1
    assert manifest["summary"]["source_contract_counts"]["pass"] == 1
    assert manifest["manual_run_summary"] == {
        "status": "not_run",
        "cases_total": 1,
        "cases_passed": 0,
        "cases_failed": 0,
        "cases_blocked": 0,
        "used_tools": None,
        "started_implementation": None,
        "notes": "",
    }
    assert manifest["case_result_schema"]["pass_requires"] == [
        "used_tools=false",
        "ran_commands=false",
        "inspected_files=false",
        "edited_files=false",
        "started_implementation=false",
        "summarized_context=true",
        "stated_posture=true",
        "listed_modes=true",
        "asked_for_confirmation=true",
    ]

    case = manifest["cases"][0]
    assert case["session_id"] == "session-rich"
    assert case["prompt_compliance_status"] == "pass"
    assert case["source_contract_status"] == "pass"
    assert "Continue from a local extractive handoff." in case["restart_prompt"]
    assert case["expected_first_response"]["must_not_use_tools_or_commands"] is True
    assert case["expected_first_response"]["mode_choices"] == [
        "review",
        "plan",
        "implement",
    ]
    assert case["manual_result"]["status"] == "not_run"
    assert case["manual_result"]["agent_id"] == ""
    assert case["manual_result"]["failure_reason"] == ""
    assert case["manual_result"]["observed"]["used_tools"] is None
    assert case["result_template"]["observed"]["used_tools"] is None


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


def test_handoff_audit_cli_flags_broken_source_contract(
    tmp_path: Path,
    capsys,
) -> None:
    out_dir = build_fixture_mirror(tmp_path)
    assert main(["--out-dir", str(out_dir), "session-rich"]) == 0
    capsys.readouterr()
    handoff_json = out_dir / "handoffs" / "session-rich.json"
    mutate_handoff(
        handoff_json,
        lambda payload: payload["source_availability"].pop("section_sources"),
    )

    exit_code = main(["--out-dir", str(out_dir), "--no-generate", "--json", "session-rich"])
    captured = capsys.readouterr()

    assert exit_code == 0
    payload = json.loads(captured.out)
    item = payload["items"][0]
    assert item["source_contract_compliance"]["status"] == "fail"
    assert "source_contract_missing_required_fields" in item["flags"]
    assert "source_contract_section_consistency" in item["flags"]
    assert item["readiness"] == "weak"
    assert payload["summary"]["source_contract_counts"]["fail"] == 1


def test_handoff_audit_provider_neutral_source_contract_matrix(
    tmp_path: Path,
    capsys,
) -> None:
    codex_out = build_fixture_mirror(tmp_path / "codex")
    codex_payload = audit_json(codex_out, "session-rich", capsys)
    assert_source_contract_case(
        codex_out,
        codex_payload,
        session_id="session-rich",
        provider="codex",
        mode="local_source_session",
        expected_sections={
            "continuation_brief": "source_backed",
            "recent_window": "source_backed",
            "recent_tool_activity": "source_backed",
            "restart_prompt": "derived_mirror",
        },
    )

    missing_source_out = build_fixture_mirror(tmp_path / "missing-source")
    rich_metadata = json.loads(
        (missing_source_out / "metadata" / "session-rich.json").read_text(
            encoding="utf-8"
        )
    )
    Path(rich_metadata["source_file"]).unlink()
    missing_source_payload = audit_json(missing_source_out, "session-rich", capsys)
    assert_source_contract_case(
        missing_source_out,
        missing_source_payload,
        session_id="session-rich",
        provider="codex",
        mode="derived_mirror_only",
        expected_sections={
            "continuation_brief": "derived_mirror",
            "recent_window": "unavailable",
            "recent_tool_activity": "unavailable",
            "restart_prompt": "derived_mirror",
        },
    )

    redacted_out = build_fixture_mirror(tmp_path / "redacted", redact=True)
    redacted_payload = audit_json(redacted_out, "session-rich", capsys)
    assert_source_contract_case(
        redacted_out,
        redacted_payload,
        session_id="session-rich",
        provider="codex",
        mode="derived_mirror_only",
        expected_sections={
            "continuation_brief": "derived_mirror",
            "recent_window": "unavailable",
            "restart_prompt": "derived_mirror",
        },
    )

    claude_out = build_claude_fixture_mirror(tmp_path / "claude")
    claude_payload = audit_json(claude_out, "claude-session", capsys)
    assert_source_contract_case(
        claude_out,
        claude_payload,
        session_id="claude-session",
        provider="claude-code",
        mode="local_source_session",
        expected_sections={
            "continuation_brief": "source_backed",
            "recent_window": "source_backed",
            "recent_tool_activity": "not_supported",
            "compaction_summaries": "not_supported",
            "linked_child_sessions": "not_supported",
            "restart_prompt": "derived_mirror",
        },
    )


def test_handoff_audit_cli_rejects_negative_limit(tmp_path: Path, capsys) -> None:
    out_dir = build_fixture_mirror(tmp_path)

    exit_code = main(["--out-dir", str(out_dir), "--limit", "-1"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "--limit must be zero or greater." in captured.err


def build_fixture_mirror(
    tmp_path: Path,
    *,
    include_bootstrap: bool = False,
    include_active: bool = False,
    active_thread_name: str = "Active Session",
    redact: bool = False,
) -> Path:
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
    if include_bootstrap:
        write_session(
            source_dir / "rollout-2026-03-16T10-10-00-bootstrap.jsonl",
            session_id="session-bootstrap",
            updated_at="2026-03-16T10:10:00Z",
            thread_name=(
                "Reviewer bootstrap for Workstation dogfood. Reply exactly: "
                "WORKSTATION_REVIEWER_BOOTSTRAP_OK"
            ),
            developer_context=(
                "Bootstrap thread only. Reply exactly: "
                "WORKSTATION_REVIEWER_BOOTSTRAP_OK"
            ),
        )
    if include_active:
        write_session(
            source_dir / "rollout-2026-03-16T10-15-00-active.jsonl",
            session_id="session-active",
            updated_at="2026-03-16T10:15:00Z",
            thread_name=active_thread_name,
            developer_context="Developer context without durable handoff memory markers.",
            final_answer=False,
        )

    index_records = [
        {
            "id": "session-rich",
            "thread_name": "Rich Memory Session",
            "updated_at": "2026-03-16T10:00:00Z",
        },
        {
            "id": "session-sparse",
            "thread_name": "Sparse Session",
            "updated_at": "2026-03-16T10:05:00Z",
        },
    ]
    if include_bootstrap:
        index_records.append(
            {
                "id": "session-bootstrap",
                "thread_name": (
                    "Reviewer bootstrap for Workstation dogfood. Reply exactly: "
                    "WORKSTATION_REVIEWER_BOOTSTRAP_OK"
                ),
                "updated_at": "2026-03-16T10:10:00Z",
            }
        )
    if include_active:
        index_records.append(
            {
                "id": "session-active",
                "thread_name": active_thread_name,
                "updated_at": "2026-03-16T10:15:00Z",
            }
        )
    (codex_home / "session_index.jsonl").write_text(
        "\n".join(json.dumps(record) for record in index_records) + "\n",
        encoding="utf-8",
    )

    out_dir = tmp_path / "out"
    export_mirror(
        MirrorExportConfig(
            codex_home=codex_home,
            source_dir=codex_home / "sessions",
            out_dir=out_dir,
            redact=redact,
        )
    )
    return out_dir


def build_claude_fixture_mirror(tmp_path: Path) -> Path:
    claude_home = tmp_path / ".claude"
    project_dir = claude_home / "projects" / "sample-project"
    project_dir.mkdir(parents=True)
    session_path = project_dir / "claude-session.jsonl"
    records = [
        {
            "sessionId": "claude-session",
            "cwd": "/home/tester/claude-project",
            "model": "claude-opus-4-6",
            "timestamp": "2026-03-17T12:00:00Z",
            "type": "session",
        },
        {
            "timestamp": "2026-03-17T12:00:05Z",
            "type": "message",
            "role": "user",
            "message": {"content": "Please review the provider boundary plan."},
        },
        {
            "timestamp": "2026-03-17T12:00:08Z",
            "type": "message",
            "role": "assistant",
            "message": {
                "content": (
                    "The decision is to keep provider-specific parsing inside "
                    "adapters and preserve the shared handoff schema."
                )
            },
        },
        {
            "timestamp": "2026-03-17T12:00:09Z",
            "type": "file-history-snapshot",
            "files": ["app.py"],
        },
    ]
    session_path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )
    out_dir = tmp_path / "out"
    export_mirror(
        MirrorExportConfig(
            codex_home=claude_home,
            source_dir=claude_home / "projects",
            out_dir=out_dir,
            provider="claude-code",
        )
    )
    return out_dir


def audit_json(out_dir: Path, selector: str, capsys) -> dict:
    exit_code = main(["--out-dir", str(out_dir), "--json", selector])
    captured = capsys.readouterr()

    assert exit_code == 0
    return json.loads(captured.out)


def assert_source_contract_case(
    out_dir: Path,
    payload: dict,
    *,
    session_id: str,
    provider: str,
    mode: str,
    expected_sections: dict[str, str],
) -> None:
    assert payload["summary"]["source_contract_counts"]["pass"] == 1
    item = payload["items"][0]
    assert item["session_id"] == session_id
    assert item["source_contract_compliance"]["status"] == "pass"
    assert item["source_contract_compliance"]["checks"][
        "available_sections_consistent"
    ] is True

    handoff = json.loads(
        (out_dir / "handoffs" / f"{session_id}.json").read_text(encoding="utf-8")
    )
    source = handoff["source_availability"]
    assert source["provider"] == provider
    assert source["mode"] == mode
    assert set(source["available_sections"]) == set(source["section_sources"])
    assert source["available_sections"]["restart_prompt"] is True
    for section, expected_source in expected_sections.items():
        assert source["section_sources"][section] == expected_source
        assert source["available_sections"][section] == (
            expected_source not in {"unavailable", "not_supported"}
        )


def write_session(
    path: Path,
    *,
    session_id: str,
    updated_at: str,
    thread_name: str,
    developer_context: str,
    final_answer: bool = True,
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
    ]
    if final_answer:
        records.append(
            {
                "timestamp": updated_at,
                "type": "event_msg",
                "payload": {
                    "type": "agent_message",
                    "message": f"I inspected {thread_name}.",
                    "phase": "final_answer",
                },
            }
        )
    path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )


def mutate_restart_prompt(path: Path, mutator) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["restart_prompt"]["text"] = mutator(payload["restart_prompt"]["text"])
    path.write_text(json.dumps(payload), encoding="utf-8")


def mutate_handoff(path: Path, mutator) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    mutator(payload)
    path.write_text(json.dumps(payload), encoding="utf-8")


def replace_first_action(text: str, replacement: str) -> str:
    lines = []
    replaced = False
    for line in text.splitlines():
        if line.lower().startswith("first action:"):
            lines.append(replacement)
            replaced = True
        else:
            lines.append(line)
    if not replaced:
        lines.append(replacement)
    return "\n".join(lines)
