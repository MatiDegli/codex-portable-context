"""Linked child (sub-agent) sessions from the local Codex state database."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..discovery import mirror_layout
from ..redaction import RedactionContext, redact_text
from .constants import LINKED_CHILD_SESSION_LIMIT
from .source import _infer_source_dir
from .state import _text_value
from .utils import _as_dict, _excerpt_text, _string


def _linked_child_sessions(
    *,
    metadata: dict[str, Any],
    out_dir: Path,
    redacted: bool,
    context: RedactionContext,
) -> list[dict[str, str]]:
    parent_session_id = _string(metadata.get("session_id"))
    codex_home = _infer_codex_home(metadata)
    if not parent_session_id or codex_home is None:
        return []

    state_path = codex_home / "state_5.sqlite"
    if not state_path.is_file():
        return []

    try:
        connection = sqlite3.connect(f"{state_path.resolve().as_uri()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        if not _has_linked_child_schema(connection):
            return []
        rows = connection.execute(
            """
            SELECT
              e.parent_thread_id,
              e.child_thread_id,
              e.status,
              t.rollout_path,
              t.updated_at,
              t.updated_at_ms,
              t.cwd,
              t.title,
              t.first_user_message,
              t.agent_nickname,
              t.agent_role
            FROM thread_spawn_edges e
            LEFT JOIN threads t ON t.id = e.child_thread_id
            WHERE e.parent_thread_id = ?
            ORDER BY COALESCE(t.updated_at_ms, t.updated_at * 1000, 0) DESC,
                     e.child_thread_id ASC
            LIMIT ?
            """,
            (parent_session_id, LINKED_CHILD_SESSION_LIMIT),
        ).fetchall()
    except (OSError, sqlite3.Error):
        return []
    finally:
        try:
            connection.close()
        except UnboundLocalError:
            pass

    return [
        _linked_child_payload(
            row,
            out_dir=out_dir,
            redacted=redacted,
            context=context,
        )
        for row in rows
    ]


def _has_linked_child_schema(connection: sqlite3.Connection) -> bool:
    edge_columns = _sqlite_table_columns(connection, "thread_spawn_edges")
    thread_columns = _sqlite_table_columns(connection, "threads")
    return {
        "parent_thread_id",
        "child_thread_id",
        "status",
    }.issubset(edge_columns) and {
        "id",
        "rollout_path",
        "updated_at",
        "updated_at_ms",
        "cwd",
        "title",
        "first_user_message",
        "agent_nickname",
        "agent_role",
    }.issubset(thread_columns)


def _sqlite_table_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    try:
        rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    except sqlite3.Error:
        return set()
    return {str(row[1]) for row in rows}


def _linked_child_payload(
    row: sqlite3.Row,
    *,
    out_dir: Path,
    redacted: bool,
    context: RedactionContext,
) -> dict[str, str]:
    child_session_id = _string(row["child_thread_id"])
    child_metadata = _load_child_mirror_metadata(out_dir, child_session_id)
    child_summary = _as_dict(child_metadata.get("summary"))
    layout = mirror_layout(out_dir)
    markdown_relpath = _string(child_metadata.get("markdown_relpath"))
    handoff_relpath = ""
    if (layout.out_dir / layout.handoff_markdown_relpath(child_session_id)).is_file():
        handoff_relpath = layout.handoff_markdown_relpath(child_session_id)

    first_user_message = _string(row["first_user_message"]) or _string(
        child_summary.get("first_user_message")
    )
    latest_assistant_message = _string(child_summary.get("last_assistant_message"))

    return {
        "parent_session_id": _clean_child_text(row["parent_thread_id"], redacted, context, 120),
        "child_session_id": child_session_id,
        "status": _clean_child_text(row["status"], redacted, context, 80),
        "title": _clean_child_text(
            _string(row["title"]) or _string(child_metadata.get("title")),
            redacted,
            context,
            140,
        ),
        "cwd": _clean_child_text(row["cwd"], redacted, context, 220),
        "rollout_path": _clean_child_text(row["rollout_path"], redacted, context, 260),
        "first_user_message": _clean_child_text(first_user_message, redacted, context, 260),
        "latest_assistant_message": _clean_child_text(
            latest_assistant_message,
            redacted,
            context,
            260,
        ),
        "updated_at": _epoch_timestamp_to_iso(row["updated_at_ms"] or row["updated_at"]),
        "agent_nickname": _clean_child_text(row["agent_nickname"], redacted, context, 80),
        "agent_role": _clean_child_text(row["agent_role"], redacted, context, 80),
        "markdown_relpath": markdown_relpath,
        "handoff_markdown_relpath": handoff_relpath,
    }


def _load_child_mirror_metadata(out_dir: Path, child_session_id: str) -> dict[str, Any]:
    if not child_session_id:
        return {}
    metadata_path = mirror_layout(out_dir).metadata_path(child_session_id)
    if not metadata_path.is_file():
        return {}
    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _clean_child_text(
    value: Any,
    redacted: bool,
    context: RedactionContext,
    limit: int,
) -> str:
    text = _text_value(value)
    if redacted:
        text = redact_text(text, context).text
    return _excerpt_text(text, limit=limit)


def _epoch_timestamp_to_iso(value: Any) -> str:
    if value in (None, ""):
        return ""
    try:
        timestamp = int(value)
    except (TypeError, ValueError):
        return _string(value)
    if timestamp > 10_000_000_000:
        timestamp = timestamp // 1000
    try:
        return (
            datetime.fromtimestamp(timestamp, tz=UTC)
            .replace(microsecond=0)
            .isoformat()
            .replace(
                "+00:00",
                "Z",
            )
        )
    except (OSError, OverflowError, ValueError):
        return ""


def _infer_codex_home(metadata: dict[str, Any]) -> Path | None:
    source_file_value = metadata.get("source_file")
    source_relpath_value = metadata.get("source_relpath")
    if not isinstance(source_file_value, str) or not source_file_value.strip():
        return None
    if not isinstance(source_relpath_value, str) or not source_relpath_value.strip():
        return None

    source_file = Path(source_file_value).expanduser().resolve(strict=False)
    source_dir = _infer_source_dir(source_file, source_relpath_value)
    if source_dir.name in {"sessions", "archived_sessions"}:
        return source_dir.parent
    return source_dir


def _child_agent_label(child: dict[str, Any]) -> str:
    nickname = _string(child.get("agent_nickname"))
    role = _string(child.get("agent_role"))
    if nickname and role:
        return f"{nickname} (`{role}`)"
    if nickname:
        return nickname
    if role:
        return f"`{role}`"
    return ""
