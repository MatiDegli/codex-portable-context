"""Bounded local control helpers built on top of MCP task-state scaffolding."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .task_state import TaskRecord, load_task_record, save_task_record, task_state_path

ControlPayload = dict[str, Any]


def enqueue_codex_prompt(
    *,
    task_id: str,
    accepted_at: str,
    working_directory: str,
    prompt: str,
    root_dir: Path | None = None,
    session_name: str | None = None,
    model_profile: str | None = None,
    execution_mode: str = "oneshot",
    timeout_seconds: int = 900,
) -> ControlPayload:
    """Persist a queued bounded task record without launching Codex."""

    record = TaskRecord.queued(
        task_id=task_id,
        accepted_at=accepted_at,
        working_directory=working_directory,
        prompt=prompt,
        execution_mode=execution_mode,
        timeout_seconds=timeout_seconds,
        session_name=session_name,
        model_profile=model_profile,
    )
    path = save_task_record(record, root_dir=root_dir)
    return {
        "task_id": record.task_id,
        "status": record.status,
        "accepted_at": record.accepted_at,
        "working_directory": record.working_directory,
        "task_state_path": str(path.resolve()),
    }


def get_codex_task_status(
    task_id: str,
    *,
    root_dir: Path | None = None,
) -> ControlPayload:
    """Return the bounded status payload for one persisted task."""

    path = task_state_path(task_id, root_dir=root_dir)
    if not path.is_file():
        return {
            "task_id": task_id,
            "status": "missing",
            "task_state_path": str(path.resolve()),
        }

    record = load_task_record(task_id, root_dir=root_dir)
    return {
        "task_id": record.task_id,
        "status": record.status,
        "accepted_at": record.accepted_at,
        "started_at": record.started_at,
        "completed_at": record.completed_at,
        "codex_session_id": record.codex_session_id,
        "working_directory": record.working_directory,
        "task_state_path": str(path.resolve()),
    }


def get_last_codex_result(
    task_id: str,
    *,
    root_dir: Path | None = None,
) -> ControlPayload:
    """Return the bounded result payload for one persisted task."""

    path = task_state_path(task_id, root_dir=root_dir)
    if not path.is_file():
        return {
            "task_id": task_id,
            "status": "missing",
            "task_state_path": str(path.resolve()),
        }

    record = load_task_record(task_id, root_dir=root_dir)
    return {
        "task_id": record.task_id,
        "status": record.status,
        "final_text": record.final_text,
        "codex_session_id": record.codex_session_id,
        "artifact_paths": list(record.artifact_paths),
        "result_summary": dict(record.result_summary),
        "task_state_path": str(path.resolve()),
    }
