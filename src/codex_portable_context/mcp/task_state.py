"""Local task-state helpers for bounded Codex CLI control scaffolding."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

TaskStatus = Literal["queued", "running", "completed", "failed", "cancelled"]
TERMINAL_TASK_STATUSES = frozenset({"completed", "failed", "cancelled"})
TASK_RETENTION_DAYS = 7


def default_task_state_root(
    *,
    platform: str | None = None,
    home_dir: Path | None = None,
    localappdata_dir: Path | None = None,
) -> Path:
    """Return the preferred local task-state root for the current platform."""

    active_platform = (platform or os.name).lower()
    home = (home_dir or Path.home()).expanduser()
    if active_platform.startswith("nt"):
        if localappdata_dir is None:
            raw_localappdata = os.environ.get("LOCALAPPDATA")
            if raw_localappdata:
                localappdata_dir = Path(raw_localappdata)
        if localappdata_dir is not None:
            return localappdata_dir / "codex-portable-context" / "mcp-tasks"
    if active_platform == "posix":
        return home / ".local" / "state" / "codex-portable-context" / "mcp-tasks"
    return home / ".codex-portable-context" / "mcp-tasks"


def task_state_path(task_id: str, *, root_dir: Path | None = None) -> Path:
    """Return the JSON state path for one task id."""

    active_root = (root_dir or default_task_state_root()).expanduser()
    return active_root / f"{task_id}.json"


def is_terminal_status(status: str) -> bool:
    """Return whether a task status is terminal."""

    return status in TERMINAL_TASK_STATUSES


def _parse_timestamp(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _retention_deadline(completed_at: str | None) -> str | None:
    if not completed_at:
        return None
    deadline = _parse_timestamp(completed_at) + timedelta(days=TASK_RETENTION_DAYS)
    return _format_timestamp(deadline)


@dataclass(frozen=True, slots=True)
class TaskRecord:
    """Small local task-state record for the first bounded control scaffold."""

    task_id: str
    status: TaskStatus
    accepted_at: str
    working_directory: str
    prompt: str
    execution_mode: str = "oneshot"
    timeout_seconds: int = 900
    session_name: str | None = None
    model_profile: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    codex_session_id: str | None = None
    final_text: str | None = None
    artifact_paths: list[str] = field(default_factory=list)
    result_summary: dict[str, Any] = field(default_factory=dict)
    prune_after: str | None = None

    @classmethod
    def queued(
        cls,
        *,
        task_id: str,
        accepted_at: str,
        working_directory: str,
        prompt: str,
        execution_mode: str = "oneshot",
        timeout_seconds: int = 900,
        session_name: str | None = None,
        model_profile: str | None = None,
    ) -> TaskRecord:
        """Create the first queued record for one bounded task."""

        return cls(
            task_id=task_id,
            status="queued",
            accepted_at=accepted_at,
            working_directory=working_directory,
            prompt=prompt,
            execution_mode=execution_mode,
            timeout_seconds=timeout_seconds,
            session_name=session_name,
            model_profile=model_profile,
        )

    def mark_running(
        self,
        *,
        started_at: str,
        codex_session_id: str | None = None,
    ) -> TaskRecord:
        """Return the running state for this task."""

        return replace(
            self,
            status="running",
            started_at=started_at,
            codex_session_id=codex_session_id,
            completed_at=None,
            prune_after=None,
        )

    def mark_completed(
        self,
        *,
        completed_at: str,
        final_text: str | None = None,
        codex_session_id: str | None = None,
        artifact_paths: list[str] | None = None,
        result_summary: dict[str, Any] | None = None,
    ) -> TaskRecord:
        """Return the completed terminal state for this task."""

        return replace(
            self,
            status="completed",
            completed_at=completed_at,
            codex_session_id=codex_session_id or self.codex_session_id,
            final_text=final_text,
            artifact_paths=list(artifact_paths or []),
            result_summary=dict(result_summary or {}),
            prune_after=_retention_deadline(completed_at),
        )

    def mark_failed(
        self,
        *,
        completed_at: str,
        result_summary: dict[str, Any] | None = None,
    ) -> TaskRecord:
        """Return the failed terminal state for this task."""

        return replace(
            self,
            status="failed",
            completed_at=completed_at,
            result_summary=dict(result_summary or {}),
            prune_after=_retention_deadline(completed_at),
        )

    def mark_cancelled(
        self,
        *,
        completed_at: str,
        result_summary: dict[str, Any] | None = None,
    ) -> TaskRecord:
        """Return the cancelled terminal state for this task."""

        return replace(
            self,
            status="cancelled",
            completed_at=completed_at,
            result_summary=dict(result_summary or {}),
            prune_after=_retention_deadline(completed_at),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the serialized JSON-safe representation."""

        return {
            "task_id": self.task_id,
            "status": self.status,
            "accepted_at": self.accepted_at,
            "working_directory": self.working_directory,
            "prompt": self.prompt,
            "execution_mode": self.execution_mode,
            "timeout_seconds": self.timeout_seconds,
            "session_name": self.session_name,
            "model_profile": self.model_profile,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "codex_session_id": self.codex_session_id,
            "final_text": self.final_text,
            "artifact_paths": list(self.artifact_paths),
            "result_summary": dict(self.result_summary),
            "prune_after": self.prune_after,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> TaskRecord:
        """Restore one task record from its JSON payload."""

        return cls(
            task_id=str(payload["task_id"]),
            status=payload["status"],
            accepted_at=str(payload["accepted_at"]),
            working_directory=str(payload["working_directory"]),
            prompt=str(payload["prompt"]),
            execution_mode=str(payload.get("execution_mode") or "oneshot"),
            timeout_seconds=int(payload.get("timeout_seconds", 900)),
            session_name=_optional_string(payload.get("session_name")),
            model_profile=_optional_string(payload.get("model_profile")),
            started_at=_optional_string(payload.get("started_at")),
            completed_at=_optional_string(payload.get("completed_at")),
            codex_session_id=_optional_string(payload.get("codex_session_id")),
            final_text=_optional_string(payload.get("final_text")),
            artifact_paths=[str(path) for path in payload.get("artifact_paths", [])],
            result_summary=dict(payload.get("result_summary") or {}),
            prune_after=_optional_string(payload.get("prune_after")),
        )


def ensure_task_state_root(root_dir: Path | None = None) -> Path:
    """Create the task-state root if needed and return it."""

    active_root = (root_dir or default_task_state_root()).expanduser()
    active_root.mkdir(parents=True, exist_ok=True)
    return active_root


def save_task_record(record: TaskRecord, *, root_dir: Path | None = None) -> Path:
    """Persist one task record as JSON and return the path."""

    active_root = ensure_task_state_root(root_dir)
    path = task_state_path(record.task_id, root_dir=active_root)
    path.write_text(
        json.dumps(record.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def load_task_record(task_id: str, *, root_dir: Path | None = None) -> TaskRecord:
    """Load one persisted task record by id."""

    path = task_state_path(task_id, root_dir=root_dir)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return TaskRecord.from_dict(payload)


def prunable_task_ids(records: list[TaskRecord], *, now_utc: str) -> list[str]:
    """Return terminal task ids eligible for pruning at the chosen time."""

    current = _parse_timestamp(now_utc)
    stale_ids: list[str] = []
    for record in records:
        if not is_terminal_status(record.status) or not record.prune_after:
            continue
        if _parse_timestamp(record.prune_after) <= current:
            stale_ids.append(record.task_id)
    return stale_ids


def _optional_string(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)
