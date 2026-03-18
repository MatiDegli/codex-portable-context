from pathlib import Path

from codex_portable_context.mcp.task_state import (
    TaskRecord,
    default_task_state_root,
    is_terminal_status,
    load_task_record,
    prunable_task_ids,
    save_task_record,
    task_state_path,
)


def test_default_task_state_root_uses_posix_state_dir(tmp_path: Path) -> None:
    root = default_task_state_root(platform="posix", home_dir=tmp_path)

    assert root == tmp_path / ".local" / "state" / "codex-portable-context" / "mcp-tasks"


def test_default_task_state_root_uses_windows_localappdata(tmp_path: Path) -> None:
    localappdata = tmp_path / "LocalAppData"

    root = default_task_state_root(
        platform="nt",
        home_dir=tmp_path / "Home",
        localappdata_dir=localappdata,
    )

    assert root == localappdata / "codex-portable-context" / "mcp-tasks"


def test_task_state_path_is_separate_from_out_dir(tmp_path: Path) -> None:
    task_root = default_task_state_root(platform="posix", home_dir=tmp_path)
    out_dir = tmp_path / "out"

    path = task_state_path("mcp-task-001", root_dir=task_root)

    assert path == task_root / "mcp-task-001.json"
    assert out_dir not in path.parents


def test_task_record_lifecycle_sets_terminal_retention() -> None:
    queued = TaskRecord.queued(
        task_id="mcp-task-001",
        accepted_at="2026-03-18T19:16:48Z",
        working_directory="/repo",
        prompt="Do one bounded task.",
    )
    running = queued.mark_running(started_at="2026-03-18T19:17:00Z", codex_session_id="session-1")
    completed = running.mark_completed(
        completed_at="2026-03-18T19:18:00Z",
        final_text="Done.",
        artifact_paths=["/tmp/result.md"],
        result_summary={"outcome": "completed", "has_final_text": True},
    )

    assert queued.status == "queued"
    assert queued.prune_after is None
    assert running.status == "running"
    assert running.codex_session_id == "session-1"
    assert completed.status == "completed"
    assert completed.completed_at == "2026-03-18T19:18:00Z"
    assert completed.prune_after == "2026-03-25T19:18:00Z"
    assert completed.result_summary["outcome"] == "completed"
    assert is_terminal_status(completed.status) is True


def test_task_record_roundtrip_persists_json_state(tmp_path: Path) -> None:
    record = TaskRecord.queued(
        task_id="mcp-task-002",
        accepted_at="2026-03-18T19:16:48Z",
        working_directory="/repo",
        prompt="Prepare one bounded task.",
        session_name="pilot",
        model_profile="default",
    ).mark_failed(
        completed_at="2026-03-18T19:20:00Z",
        result_summary={"outcome": "failed"},
    )

    path = save_task_record(record, root_dir=tmp_path / "task-state")
    restored = load_task_record("mcp-task-002", root_dir=tmp_path / "task-state")

    assert path.is_file()
    assert restored == record


def test_prunable_task_ids_filters_terminal_records_only() -> None:
    completed = TaskRecord.queued(
        task_id="done-task",
        accepted_at="2026-03-18T19:16:48Z",
        working_directory="/repo",
        prompt="Do one bounded task.",
    ).mark_completed(
        completed_at="2026-03-18T19:18:00Z",
        final_text="Done.",
    )
    running = TaskRecord.queued(
        task_id="running-task",
        accepted_at="2026-03-18T19:16:48Z",
        working_directory="/repo",
        prompt="Still running.",
    ).mark_running(started_at="2026-03-18T19:17:00Z")

    stale = prunable_task_ids(
        [completed, running],
        now_utc="2026-03-25T19:18:00Z",
    )

    assert stale == ["done-task"]
