from pathlib import Path

from codex_portable_context.mcp.control import (
    enqueue_codex_prompt,
    get_codex_task_status,
    get_last_codex_result,
)
from codex_portable_context.mcp.task_state import TaskRecord, save_task_record


def test_enqueue_codex_prompt_persists_queued_task_without_launching_codex(
    tmp_path: Path,
) -> None:
    payload = enqueue_codex_prompt(
        task_id="mcp-task-003",
        accepted_at="2026-03-18T19:21:03Z",
        working_directory=str(tmp_path / "repo"),
        prompt="Do one bounded task.",
        root_dir=tmp_path / "task-state",
        session_name="pilot",
        model_profile="default",
    )

    assert payload["task_id"] == "mcp-task-003"
    assert payload["status"] == "queued"
    assert payload["accepted_at"] == "2026-03-18T19:21:03Z"
    assert Path(payload["task_state_path"]).is_file()


def test_get_codex_task_status_returns_missing_for_unknown_task(tmp_path: Path) -> None:
    payload = get_codex_task_status("missing-task", root_dir=tmp_path / "task-state")

    assert payload["task_id"] == "missing-task"
    assert payload["status"] == "missing"


def test_get_codex_task_status_reads_persisted_running_state(tmp_path: Path) -> None:
    record = TaskRecord.queued(
        task_id="mcp-task-004",
        accepted_at="2026-03-18T19:21:03Z",
        working_directory="/repo",
        prompt="Do one bounded task.",
    ).mark_running(
        started_at="2026-03-18T19:22:00Z",
        codex_session_id="session-004",
    )
    save_task_record(record, root_dir=tmp_path / "task-state")

    payload = get_codex_task_status("mcp-task-004", root_dir=tmp_path / "task-state")

    assert payload["status"] == "running"
    assert payload["started_at"] == "2026-03-18T19:22:00Z"
    assert payload["codex_session_id"] == "session-004"


def test_get_last_codex_result_returns_bounded_result_metadata(tmp_path: Path) -> None:
    record = TaskRecord.queued(
        task_id="mcp-task-005",
        accepted_at="2026-03-18T19:21:03Z",
        working_directory="/repo",
        prompt="Do one bounded task.",
    ).mark_completed(
        completed_at="2026-03-18T19:23:00Z",
        final_text="Done.",
        codex_session_id="session-005",
        artifact_paths=["/tmp/result.md"],
        result_summary={"outcome": "completed", "has_final_text": True},
    )
    save_task_record(record, root_dir=tmp_path / "task-state")

    payload = get_last_codex_result("mcp-task-005", root_dir=tmp_path / "task-state")

    assert payload["task_id"] == "mcp-task-005"
    assert payload["status"] == "completed"
    assert payload["final_text"] == "Done."
    assert payload["codex_session_id"] == "session-005"
    assert payload["artifact_paths"] == ["/tmp/result.md"]
    assert payload["result_summary"]["has_final_text"] is True
