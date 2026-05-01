import json
import sqlite3
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
        == "Why is the IDE output empty?"
    )
    assert payload["current_state"]["status"] == "in_progress"
    assert (
        payload["current_state"]["current_focus"]
        == "Why is the IDE output empty?"
    )
    assert (
        payload["current_state"]["next_recommended_action"]
        == (
            "Start a fresh local session and continue from this handoff's "
            "Current State and Open Loops."
        )
    )
    assert (
        payload["continuation_brief"]["next_best_action"]
        == (
            "Inspect `README.md` first, then recover the current unresolved "
            "state before choosing review, plan, or implement."
        )
    )
    assert payload["continuation_brief"]["what_we_were_doing"] == "Why is the IDE output empty?"
    assert payload["continuation_brief"]["latest_resolved_request"] == ""
    assert (
        payload["resolved_state"]["latest_user_request"]
        == "Why is the IDE output empty?"
    )
    assert payload["resolved_state"]["request_resolution_status"] == "unanswered"
    assert payload["resolved_state"]["validation_summary"] == "ran ./scripts/validate-python-v2"
    assert payload["restart_prompt"]["kind"] == "fresh_session_reentry"
    assert payload["reentry_posture"]["initial_mode"] == "read_only_context_retrieval"
    assert payload["reentry_posture"]["requires_confirmation_before_changes"] is True
    assert "run_commands" in payload["reentry_posture"]["forbidden_first_turn_actions"]
    assert payload["decisions_and_invariants"]["confidence"] in {"low", "medium", "high"}
    changed_paths = {
        item["path"]: item
        for item in payload["changed_artifacts"]["changed_paths"]
    }
    assert changed_paths["README.md"]["source"] == "tool_output_updated_files"
    assert "README.md" in payload["changed_artifacts"]["recommended_inspection_order"]
    assert "Continue from a local extractive handoff." in payload["restart_prompt"]["text"]
    assert "Initial operating mode: read-only context retrieval and review only." in (
        payload["restart_prompt"]["text"]
    )
    assert "Do not run commands" in payload["restart_prompt"]["text"]
    assert "Ask the user to choose one mode" in payload["restart_prompt"]["text"]
    assert "Required first response format:" in payload["restart_prompt"]["text"]
    assert "Do not skip any section" in payload["restart_prompt"]["text"]
    assert "Session ID: session-5678" in payload["restart_prompt"]["text"]
    assert "Linked child sessions:" in payload["restart_prompt"]["text"]
    assert "Child Fixture Session" in payload["restart_prompt"]["text"]
    assert "Changed / key artifacts:" in payload["restart_prompt"]["text"]
    assert "Decisions and invariants:" in payload["restart_prompt"]["text"]
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
    assert payload["open_loops"]["open_question"] == "Why is the IDE output empty?"
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
    assert payload["compaction_summaries"] == [
        {
            "timestamp": "2026-03-16T10:05:01Z",
            "source": "context_compacted",
            "summary": (
                "The session established that the fixture repo should be inspected "
                "before continuing."
            ),
            "prompt": "Continue from the fixture inspection context.",
        }
    ]
    assert payload["linked_child_sessions"] == [
        {
            "parent_session_id": "session-5678",
            "child_session_id": "session-child-1",
            "status": "closed",
            "title": "Child Fixture Session",
            "cwd": "/home/tester/project",
            "rollout_path": str(
                tmp_path
                / ".codex"
                / "sessions"
                / "2026"
                / "03"
                / "16"
                / "rollout-2026-03-16T10-04-00-child-session.jsonl"
            ),
            "first_user_message": "Please draft the child fixture slice.",
            "latest_assistant_message": "I will inspect Child Fixture Session.",
            "updated_at": "2026-03-16T10:04:59Z",
            "agent_nickname": "Fixture",
            "agent_role": "worker",
            "markdown_relpath": "sessions/session-child-1.md",
            "handoff_markdown_relpath": "",
        }
    ]
    assert payload["recent_window"]
    assert any(
        "Please inspect Second Fixture Session." in item["text"]
        for item in payload["recent_window"]
    )

    markdown = (out_dir / "handoffs" / "session-5678.md").read_text(encoding="utf-8")
    reader = (out_dir / "reader" / "session-5678.html").read_text(encoding="utf-8")
    assert "## Continuation Brief" in markdown
    assert "## Resolved State" in markdown
    assert "## Re-Entry Posture" in markdown
    assert "## Changed / Key Artifacts" in markdown
    assert "README.md" in markdown
    assert "## Decisions / Invariants" in markdown
    assert "## Restart Prompt" in markdown
    assert "Do not use tools or inspect files in the first response." in markdown
    assert "```text" in markdown
    assert "## Current State" in markdown
    assert "## Continuity Entry" in markdown
    assert "Last substantive user request" in markdown
    assert "## Compaction Summaries" in markdown
    assert "Continue from the fixture inspection context." in markdown
    assert "## Linked Child Sessions" in markdown
    assert "Child Fixture Session" in markdown
    assert "## Recent Actions (normalized)" in markdown
    assert "### Destination Workflow" in markdown
    assert "## Open Loops / Risks" in markdown
    assert "Handoff JSON" in markdown
    assert "Recent Tool Activity (audit trail)" in markdown
    assert "Copy Restart Prompt" in reader
    assert "restart-prompt-text" in reader
    assert "Continue from a local extractive handoff." in reader


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
    assert payload["session"]["last_substantive_user_request"] == "Please inspect Fixture Session."
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


def test_handoff_cli_prints_restart_prompt_only(
    tmp_path: Path,
    capsys,
) -> None:
    out_dir = build_fixture_mirror(tmp_path)

    exit_code = main(["--out-dir", str(out_dir), "session-5678", "--restart-prompt"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Continue from a local extractive handoff." in captured.out
    assert "Session ID: session-5678" in captured.out
    assert "First response contract:" in captured.out
    assert "Required first response format:" in captured.out
    assert str(out_dir / "handoffs" / "session-5678.md") not in captured.out


def test_handoff_cli_rejects_print_and_restart_prompt_together(
    tmp_path: Path,
    capsys,
) -> None:
    out_dir = build_fixture_mirror(tmp_path)

    exit_code = main(
        ["--out-dir", str(out_dir), "session-5678", "--print", "--restart-prompt"]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Use only one of --print or --restart-prompt." in captured.err


def test_handoff_cli_cleans_ide_wrapper_request_when_source_missing(
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
        / "rollout-2026-03-16T10-05-00-fixture-session-b.jsonl"
    )
    source_file.unlink()

    exit_code = main(["--out-dir", str(out_dir), "session-5678"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Handoff bundle written:" in captured.out

    payload = json.loads((out_dir / "handoffs" / "session-5678.json").read_text(encoding="utf-8"))
    assert payload["source_availability"]["available"] is False
    assert payload["session"]["last_substantive_user_request"] == "Why is the IDE output empty?"
    assert payload["current_state"]["current_focus"] == "Why is the IDE output empty?"
    assert "# Context from my IDE setup" not in payload["session"]["last_substantive_user_request"]


def test_handoff_cli_recent_actions_look_back_past_trailing_noise(
    tmp_path: Path,
    capsys,
) -> None:
    out_dir = build_fixture_mirror(tmp_path, trailing_noop_pairs=25)

    exit_code = main(["--out-dir", str(out_dir), "--latest"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Handoff bundle written:" in captured.out

    payload = json.loads((out_dir / "handoffs" / "session-5678.json").read_text(encoding="utf-8"))
    assert "ran ./scripts/validate-python-v2" in payload["recent_actions"]
    assert "updated README.md" in payload["recent_actions"]


def test_handoff_cli_marks_question_answered_after_final_response(
    tmp_path: Path,
    capsys,
) -> None:
    out_dir = build_fixture_mirror(tmp_path, final_answer_after_request=True)

    exit_code = main(["--out-dir", str(out_dir), "--latest"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Handoff bundle written:" in captured.out

    payload = json.loads((out_dir / "handoffs" / "session-5678.json").read_text(encoding="utf-8"))
    assert payload["resolved_state"]["request_resolution_status"] == "handled_with_changes"
    assert (
        payload["continuation_brief"]["latest_resolved_request"]
        == "Why is the IDE output empty?"
    )
    assert (
        payload["continuation_brief"]["next_best_action"]
        == (
            "Inspect `README.md` first, then continue the scoped follow-up from "
            "the resolved state."
        )
    )
    assert payload["open_loops"]["open_question"] == "none"

    markdown = (out_dir / "handoffs" / "session-5678.md").read_text(encoding="utf-8")
    assert "- Request resolution status: `handled_with_changes`" in markdown
    assert "The final answer explains why the IDE output was empty." in markdown


def test_handoff_cli_filters_command_paths_and_prefers_resolution_outcome(
    tmp_path: Path,
    capsys,
) -> None:
    out_dir = build_fixture_mirror(
        tmp_path,
        final_answer_after_request=True,
        final_answer_message=(
            "Implemented the Slack bound-thread sync slice.\n\n"
            "New command:\n"
            "```bash\n"
            "workstation slack sync-bound-thread --repo-root /path/to/repo "
            "--binding-id SLK-BIND-001 --json\n"
            "```\n\n"
            "It reads `.workstation/.env`, but leaves `.agent-bridge/` and "
            "`workflow/` outside the commit.\n\n"
            "Changed file: [sync.py](/home/tester/project/src/workstation/slack/sync.py)."
        ),
    )

    exit_code = main(["--out-dir", str(out_dir), "--latest"])
    capsys.readouterr()

    assert exit_code == 0
    payload = json.loads((out_dir / "handoffs" / "session-5678.json").read_text(encoding="utf-8"))
    recommended = payload["changed_artifacts"]["recommended_inspection_order"]
    assert payload["current_state"]["last_meaningful_outcome"].startswith(
        "Implemented the Slack bound-thread sync slice."
    )
    assert not any(path.startswith("bash") for path in recommended)
    assert not any(" --repo-root " in path for path in recommended)
    assert ".workstation/.env" not in recommended
    assert ".agent-bridge/" not in recommended
    assert "workflow/" not in recommended
    assert "/home/tester/project/src/workstation/slack/sync.py" in recommended


def test_handoff_cli_resolves_bare_updated_files_from_repo_root(
    tmp_path: Path,
    capsys,
) -> None:
    linked_handoff_path = repo_root() / "src/codex_portable_context/core/handoff.py"
    out_dir = build_fixture_mirror(
        tmp_path,
        final_answer_after_request=True,
        final_answer_message=(
            "Updated the handoff artifact parser and tests.\n\n"
            f"Changed file: [handoff.py]({linked_handoff_path}:10).\n"
            "Ignore noisy terminal artifacts like "
            "`/home/matidegli/.cache/starship/session_123456.log` and `48/48`."
        ),
        tool_updated_files=("handoff.py", "test_cli_handoff.py"),
    )

    exit_code = main(["--out-dir", str(out_dir), "--latest"])
    capsys.readouterr()

    assert exit_code == 0
    payload = json.loads((out_dir / "handoffs" / "session-5678.json").read_text(encoding="utf-8"))
    changed = {
        item["path"]
        for item in payload["changed_artifacts"]["changed_paths"]
        if item["source"] == "tool_output_updated_files"
    }
    recommended = payload["changed_artifacts"]["recommended_inspection_order"]
    assert "handoff.py" in changed
    assert "tests/test_cli_handoff.py" in changed
    assert "src/codex_portable_context/core/handoff.py" in recommended
    assert not any(str(repo_root()) in path for path in recommended)
    assert not any("starship" in path for path in recommended)
    assert "48/48" not in recommended
    assert "handoff.py" not in recommended
    assert "/" not in recommended


def test_handoff_cli_expands_contextual_short_follow_up(
    tmp_path: Path,
    capsys,
) -> None:
    out_dir = build_fixture_mirror(
        tmp_path,
        wrapped_request="Pasamelo",
        prior_wrapped_request="Which agent should receive the scoring prompt?",
        final_answer_after_request=True,
    )

    exit_code = main(["--out-dir", str(out_dir), "--latest"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Handoff bundle written:" in captured.out

    payload = json.loads((out_dir / "handoffs" / "session-5678.json").read_text(encoding="utf-8"))
    assert payload["resolved_state"]["latest_user_request"] == "Pasamelo"
    assert (
        payload["resolved_state"]["previous_user_request"]
        == "Which agent should receive the scoring prompt?"
    )
    assert payload["resolved_state"]["latest_user_request_is_context_dependent"] == "yes"
    assert (
        payload["resolved_state"]["contextual_user_request"]
        == "Which agent should receive the scoring prompt? Follow-up request: Pasamelo"
    )
    assert (
        payload["continuation_brief"]["what_we_were_doing"]
        == "Which agent should receive the scoring prompt? Follow-up request: Pasamelo"
    )
    assert (
        payload["continuation_brief"]["latest_resolved_request"]
        == "Which agent should receive the scoring prompt? Follow-up request: Pasamelo"
    )

    markdown = (out_dir / "handoffs" / "session-5678.md").read_text(encoding="utf-8")
    assert "- Latest user request: Pasamelo" in markdown
    assert (
        "- Contextual user request: Which agent should receive the scoring prompt? "
        "Follow-up request: Pasamelo"
    ) in markdown


def test_handoff_cli_expands_long_pasamelo_follow_up(
    tmp_path: Path,
    capsys,
) -> None:
    out_dir = build_fixture_mirror(
        tmp_path,
        wrapped_request="Pasamelo, and include subagents for recursive research.",
        prior_wrapped_request="Should we write a research prompt first?",
        final_answer_after_request=True,
    )

    exit_code = main(["--out-dir", str(out_dir), "--latest"])
    capsys.readouterr()

    assert exit_code == 0
    payload = json.loads((out_dir / "handoffs" / "session-5678.json").read_text(encoding="utf-8"))
    assert payload["resolved_state"]["latest_user_request_is_context_dependent"] == "yes"
    assert (
        payload["resolved_state"]["contextual_user_request"]
        == (
            "Should we write a research prompt first? Follow-up request: "
            "Pasamelo, and include subagents for recursive research."
        )
    )


def test_handoff_cli_extracts_decisions_and_invariants(
    tmp_path: Path,
    capsys,
) -> None:
    out_dir = build_fixture_mirror(
        tmp_path,
        wrapped_request="Review candidate supply and descriptor architecture.",
        final_answer_after_request=True,
        final_answer_message=(
            "What we learned:\n"
            "- pairwise_char_semantic_rescue_v1 prueba que p17 needs a separate "
            "semantic lane.\n"
            "- It is not deployable yet because candidate supply is still limited.\n"
            "- The next step is to review the descriptor architecture before "
            "implementation.\n\n"
            "Now continue from that posture."
        ),
    )

    exit_code = main(["--out-dir", str(out_dir), "--latest"])
    capsys.readouterr()

    assert exit_code == 0
    payload = json.loads((out_dir / "handoffs" / "session-5678.json").read_text(encoding="utf-8"))
    memory = payload["decisions_and_invariants"]
    all_statements = " ".join(
        item["statement"]
        for key in ("decisions", "invariants", "rejected_paths", "open_architecture_questions")
        for item in memory[key]
    )
    assert "separate semantic lane" in all_statements
    assert "candidate supply" in all_statements
    assert "not deployable" in all_statements
    assert "descriptor architecture" in all_statements
    assert "# Context from my IDE setup" not in all_statements
    assert "## My request for Codex" not in all_statements
    assert "Now continue" not in all_statements
    assert payload["reentry_posture"]["role_hint"] == "architect_reviewer"
    assert "Decisions and invariants:" in payload["restart_prompt"]["text"]
    assert "candidate supply" in payload["restart_prompt"]["text"]


def test_handoff_cli_extracts_structural_context_decisions(
    tmp_path: Path,
    capsys,
) -> None:
    out_dir = build_fixture_mirror(
        tmp_path,
        developer_context=(
            "You are the cross-repo architect.\n\n"
            "## Stable boundary\n\n"
            "- `workstation-public` explicitly does NOT own:\n"
            "  - provider/session/thread transport\n"
            "  - workflow runtime\n"
            "- repo/workflow truth remains repo-owned\n\n"
            "## Strategic decisions already made\n\n"
            "1. The new thread/session communication layer should NOT live in "
            "`workstation-public`.\n"
            "2. We explicitly chose a new repo for clean separation from day one.\n"
            "3. The correct target is a transport/control layer, not a panel UI first.\n"
        ),
        final_answer_after_request=True,
        final_answer_message=(
            "The final answer handled a small follow-up without restating boundaries."
        ),
    )

    exit_code = main(["--out-dir", str(out_dir), "--latest"])
    capsys.readouterr()

    assert exit_code == 0
    payload = json.loads((out_dir / "handoffs" / "session-5678.json").read_text(encoding="utf-8"))
    memory = payload["decisions_and_invariants"]
    all_statements = " ".join(
        item["statement"]
        for key in ("decisions", "invariants", "rejected_paths", "open_architecture_questions")
        for item in memory[key]
    )
    assert "provider/session/thread transport" in all_statements
    assert "repo/workflow truth remains repo-owned" in all_statements
    assert "new repo for clean separation" in all_statements
    assert "transport/control layer" in all_statements
    assert payload["reentry_posture"]["role_hint"] == "architect_reviewer"
    assert "context_structural_memory" in memory["evidence"][0]


def test_handoff_cli_extracts_review_findings_and_risks(
    tmp_path: Path,
    capsys,
) -> None:
    out_dir = build_fixture_mirror(
        tmp_path,
        wrapped_request="Review the bounded recovery slice.",
        final_answer_after_request=True,
        final_answer_message=(
            "**Findings**\n"
            "- Medium: public docs say one recovery retry, but implementation permits "
            "arbitrary positive retry counts.\n"
            "- Medium: malformed recovery state resets the retry counter instead of "
            "failing closed.\n\n"
            "**Residual Risks**\n"
            "- No coverage for corrupt recovery state.\n\n"
            "**Recommendation**\n"
            "- Validate retry limits before enabling bounded recovery."
        ),
    )

    exit_code = main(["--out-dir", str(out_dir), "--latest"])
    capsys.readouterr()

    assert exit_code == 0
    payload = json.loads((out_dir / "handoffs" / "session-5678.json").read_text(encoding="utf-8"))
    memory = payload["decisions_and_invariants"]
    all_statements = " ".join(
        item["statement"]
        for key in ("decisions", "invariants", "rejected_paths", "open_architecture_questions")
        for item in memory[key]
    )
    assert "public docs say one recovery retry" in all_statements
    assert "malformed recovery state" in all_statements
    assert "corrupt recovery state" in all_statements
    assert "Validate retry limits" in all_statements
    assert any("review_memory" in item for item in memory["evidence"])
    assert "Open questions / risks:" in payload["restart_prompt"]["text"]
    assert "corrupt recovery state" in payload["restart_prompt"]["text"]
    assert payload["continuation_brief"]["next_best_action"].startswith(
        "Address the leading open risk or question before taking a new "
        "implementation step: No coverage for corrupt recovery state"
    )


def test_handoff_cli_uses_review_recommendation_for_next_action(
    tmp_path: Path,
    capsys,
) -> None:
    out_dir = build_fixture_mirror(
        tmp_path,
        wrapped_request="Review descriptor coverage.",
        final_answer_after_request=True,
        final_answer_message=(
            "**Recommendation**\n"
            "- Validate descriptor coverage before widening retrieval."
        ),
    )

    exit_code = main(["--out-dir", str(out_dir), "--latest"])
    capsys.readouterr()

    assert exit_code == 0
    payload = json.loads((out_dir / "handoffs" / "session-5678.json").read_text(encoding="utf-8"))
    assert (
        payload["continuation_brief"]["next_best_action"]
        == (
            "Continue from the captured recommendation: Validate descriptor "
            "coverage before widening retrieval."
        )
    )


def test_handoff_cli_extracts_implementation_outcome_memory(
    tmp_path: Path,
    capsys,
) -> None:
    out_dir = build_fixture_mirror(
        tmp_path,
        wrapped_request="Apply the materialize follow-up.",
        final_answer_after_request=True,
        final_answer_message=(
            "Implemented and committed `0158972 Clarify zero-write proposal "
            "materialization`.\n\n"
            "Changed:\n"
            "- `src/workstation/slice_proposals.py`\n"
            "- `tests/test_slice_proposals.py`\n\n"
            "Behavior now:\n"
            "- Ready proposals with no writable create actions return "
            "`noop_no_writable_deliverable`.\n"
            "- Materialization summaries report `created_count=0` without treating "
            "that as a failure.\n\n"
            "Known caveat:\n"
            "- Existing proposal fixtures still do not cover corrupt metadata.\n\n"
            "Validation:\n"
            "- ran `python -m pytest -q`"
        ),
    )

    exit_code = main(["--out-dir", str(out_dir), "--latest"])
    capsys.readouterr()

    assert exit_code == 0
    payload = json.loads((out_dir / "handoffs" / "session-5678.json").read_text(encoding="utf-8"))
    memory = payload["decisions_and_invariants"]
    all_statements = " ".join(
        item["statement"]
        for key in ("decisions", "invariants", "rejected_paths", "open_architecture_questions")
        for item in memory[key]
    )
    assert "Clarify zero-write proposal materialization" in all_statements
    assert "noop_no_writable_deliverable" in all_statements
    assert "created_count=0" in all_statements
    assert "corrupt metadata" in all_statements
    assert "python -m pytest" not in all_statements
    assert any("implementation_outcome" in item for item in memory["evidence"])
    assert payload["decisions_and_invariants"]["confidence"] == "high"
    assert payload["continuation_brief"]["next_best_action"].startswith(
        "Address the leading open risk or question before taking a new "
        "implementation step: Existing proposal fixtures still do not cover "
        "corrupt metadata"
    )


def test_handoff_cli_bootstrap_prompt_avoids_artifact_next_action(
    tmp_path: Path,
    capsys,
) -> None:
    out_dir = build_fixture_mirror(
        tmp_path,
        wrapped_request=(
            "Reviewer bootstrap for Workstation dogfood. Reply exactly: "
            "WORKSTATION_REVIEWER_BOOTSTRAP_OK"
        ),
        final_answer_after_request=True,
        final_answer_message="WORKSTATION_REVIEWER_BOOTSTRAP_OK",
    )

    exit_code = main(["--out-dir", str(out_dir), "--latest"])
    capsys.readouterr()

    assert exit_code == 0
    payload = json.loads((out_dir / "handoffs" / "session-5678.json").read_text(encoding="utf-8"))
    next_action = payload["continuation_brief"]["next_best_action"]
    assert next_action == (
        "This was a bootstrap/ACK session; no substantive continuation is "
        "expected unless the user asks for follow-up work."
    )
    assert not next_action.startswith("Inspect ")


def build_fixture_mirror(
    tmp_path: Path,
    *,
    trailing_noop_pairs: int = 0,
    final_answer_after_request: bool = False,
    final_answer_message: str = "The final answer explains why the IDE output was empty.",
    wrapped_request: str = "Why is the IDE output empty?",
    prior_wrapped_request: str = "",
    developer_context: str = "",
    tool_updated_files: tuple[str, ...] = ("README.md",),
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
    write_session(
        source_dir / "rollout-2026-03-16T10-05-00-fixture-session-b.jsonl",
        session_id="session-5678",
        updated_at="2026-03-16T10:05:06Z",
        thread_name="Second Fixture Session",
        cwd=str(repo_root()),
        wrapped_request=wrapped_request,
        prior_wrapped_request=prior_wrapped_request,
        include_turn_aborted=True,
        trailing_noop_pairs=trailing_noop_pairs,
        final_answer_after_request=final_answer_after_request,
        final_answer_message=final_answer_message,
        developer_context=developer_context,
        tool_updated_files=tool_updated_files,
    )
    write_session(
        source_dir / "rollout-2026-03-16T10-04-00-child-session.jsonl",
        session_id="session-child-1",
        updated_at="2026-03-16T10:04:59Z",
        thread_name="Child Fixture Session",
        cwd="/home/tester/project",
        wrapped_request="Draft the child fixture slice.",
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
                json.dumps(
                    {
                        "id": "session-child-1",
                        "thread_name": "Child Fixture Session",
                        "updated_at": "2026-03-16T10:04:59Z",
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
    write_thread_state(codex_home)
    return out_dir


def write_thread_state(codex_home: Path) -> None:
    database_path = codex_home / "state_5.sqlite"
    child_rollout_path = (
        codex_home
        / "sessions"
        / "2026"
        / "03"
        / "16"
        / "rollout-2026-03-16T10-04-00-child-session.jsonl"
    )
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE thread_spawn_edges (
              parent_thread_id TEXT NOT NULL,
              child_thread_id TEXT NOT NULL PRIMARY KEY,
              status TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE threads (
              id TEXT PRIMARY KEY,
              rollout_path TEXT NOT NULL,
              created_at INTEGER NOT NULL,
              updated_at INTEGER NOT NULL,
              source TEXT NOT NULL,
              model_provider TEXT NOT NULL,
              cwd TEXT NOT NULL,
              title TEXT NOT NULL,
              sandbox_policy TEXT NOT NULL,
              approval_mode TEXT NOT NULL,
              first_user_message TEXT NOT NULL,
              agent_nickname TEXT,
              agent_role TEXT,
              updated_at_ms INTEGER
            )
            """
        )
        connection.execute(
            """
            INSERT INTO thread_spawn_edges (
              parent_thread_id,
              child_thread_id,
              status
            ) VALUES (?, ?, ?)
            """,
            ("session-5678", "session-child-1", "closed"),
        )
        connection.execute(
            """
            INSERT INTO threads (
              id,
              rollout_path,
              created_at,
              updated_at,
              source,
              model_provider,
              cwd,
              title,
              sandbox_policy,
              approval_mode,
              first_user_message,
              agent_nickname,
              agent_role,
              updated_at_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "session-child-1",
                str(child_rollout_path),
                1773655499,
                1773655499,
                "codex_vscode",
                "openai",
                "/home/tester/project",
                "Child Fixture Session",
                "workspace-write",
                "never",
                "Please draft the child fixture slice.",
                "Fixture",
                "worker",
                1773655499000,
            ),
        )


def write_session(
    path: Path,
    *,
    session_id: str,
    updated_at: str,
    thread_name: str,
    cwd: str = "/home/tester/project",
    wrapped_request: str = "Proceed",
    prior_wrapped_request: str = "",
    include_turn_aborted: bool = False,
    trailing_noop_pairs: int = 0,
    final_answer_after_request: bool = False,
    final_answer_message: str = "The final answer explains why the IDE output was empty.",
    developer_context: str = "",
    tool_updated_files: tuple[str, ...] = ("README.md",),
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
                        "text": developer_context or f"Developer context for {thread_name}.",
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
        *(
            [
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
                            f"## My request for Codex:\n{prior_wrapped_request}"
                        ),
                    },
                }
            ]
            if prior_wrapped_request
            else []
        ),
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
            "timestamp": "2026-03-16T10:05:01Z",
            "type": "event_msg",
            "payload": {
                "type": "context_compacted",
                "summary": (
                    "The session established that the fixture repo should be "
                    "inspected before continuing."
                ),
                "prompt": "Continue from the fixture inspection context.",
            },
        },
        *(
            [
                {
                    "timestamp": "2026-03-16T10:05:02Z",
                    "type": "event_msg",
                    "payload": {
                        "type": "turn_aborted",
                        "reason": "fixture interruption",
                    },
                }
            ]
            if include_turn_aborted
            else []
        ),
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
                "output": _updated_files_output(tool_updated_files),
            },
        },
    ]
    if final_answer_after_request:
        records.append(
            {
                "timestamp": "2026-03-16T10:05:07Z",
                "type": "event_msg",
                "payload": {
                    "type": "agent_message",
                    "message": final_answer_message,
                    "phase": "final_answer",
                },
            }
        )
    for index in range(trailing_noop_pairs):
        call_id = f"noop-{session_id}-{index}"
        timestamp = f"2026-03-16T10:05:{10 + index:02d}Z"
        records.extend(
            [
                {
                    "timestamp": timestamp,
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "exec_command",
                        "call_id": call_id,
                        "arguments": json.dumps(
                            {"cmd": "echo noop", "workdir": "/home/tester/project"}
                        ),
                    },
                },
                {
                    "timestamp": timestamp,
                    "type": "response_item",
                    "payload": {
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": "noop\n",
                    },
                },
            ]
        )
    path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )


def _updated_files_output(paths: tuple[str, ...]) -> str:
    lines = ["Success. Updated the following files:"]
    lines.extend(f"M {path}" for path in paths)
    return "\n".join(lines) + "\n"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]
