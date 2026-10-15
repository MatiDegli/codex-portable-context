"""Continuity freshness: newer sessions and timestamps."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from ..index import load_index
from ..parsing import ParsedSession
from .utils import _string, _timestamp_after


def _build_continuity_freshness(
    *,
    metadata: dict[str, Any],
    parsed: ParsedSession | None,
    repo_state: dict[str, Any],
    out_dir: Path,
    linked_child_sessions: list[dict[str, str]],
) -> dict[str, str]:
    session_updated_at = _handoff_session_updated_at(metadata, parsed)
    repo_head_date = _string(repo_state.get("repo_head_commit_date"))
    newer_sessions = _newer_same_cwd_sessions(
        metadata=metadata,
        out_dir=out_dir,
        session_updated_at=session_updated_at,
        linked_child_sessions=linked_child_sessions,
    )
    repo_advanced = _timestamp_after_with_tolerance(
        repo_head_date,
        session_updated_at,
        tolerance=timedelta(minutes=5),
    )

    latest_same_cwd = newer_sessions[0] if newer_sessions else {}
    latest_same_cwd_id = _string(latest_same_cwd.get("session_id"))
    latest_same_cwd_updated_at = _string(latest_same_cwd.get("updated_at"))

    warnings: list[str] = []
    if latest_same_cwd_id:
        warnings.append(
            "A newer exported session uses the same working directory "
            f"({latest_same_cwd_id} at {latest_same_cwd_updated_at})."
        )
    if repo_advanced:
        warnings.append(
            "The current repo HEAD commit is newer than this session's exported "
            "conversation timestamp."
        )

    if latest_same_cwd_id and repo_advanced:
        status = "stale_newer_same_cwd_and_repo_advanced"
    elif latest_same_cwd_id:
        status = "stale_newer_same_cwd_session"
    elif repo_advanced:
        status = "stale_repo_advanced_after_session"
    elif not session_updated_at:
        status = "unknown"
    else:
        status = "fresh"

    if warnings:
        recommendation = (
            "Treat this handoff as potentially stale. Start in review or plan "
            "mode, inspect the latest same-repo session or committed roadmap, "
            "and do not implement from the old continuation brief until the "
            "user confirms the active line."
        )
    elif status == "unknown":
        recommendation = (
            "Timestamp freshness could not be verified; use the restart prompt's "
            "read-only first turn before acting."
        )
    else:
        recommendation = "No freshness warning detected."

    return {
        "status": status,
        "warning": " ".join(warnings) if warnings else "none",
        "session_updated_at": session_updated_at,
        "repo_head_commit_date": repo_head_date,
        "latest_same_cwd_session_id": latest_same_cwd_id,
        "latest_same_cwd_updated_at": latest_same_cwd_updated_at,
        "recommendation": recommendation,
    }


def _handoff_session_updated_at(
    metadata: dict[str, Any],
    parsed: ParsedSession | None,
) -> str:
    candidates = [_string(metadata.get("updated_at")), _string(metadata.get("session_timestamp"))]
    if parsed:
        candidates.append(_best_parsed_timestamp(parsed))
    return _max_iso_timestamp(candidates)


def _best_parsed_timestamp(parsed: ParsedSession) -> str:
    candidates = [_string(parsed.session_timestamp)]
    candidates.extend(_string(block.timestamp) for block in parsed.context_entries)
    candidates.extend(_string(block.timestamp) for block in parsed.conversation_entries)
    candidates.extend(_string(block.timestamp) for block in parsed.notable_events)
    return _max_iso_timestamp(candidates)


def _max_iso_timestamp(candidates: list[str]) -> str:
    best_text = ""
    best_dt: datetime | None = None
    fallback: list[str] = []
    for candidate in candidates:
        text = _string(candidate)
        if not text:
            continue
        parsed = _parse_iso_timestamp(text)
        if parsed is None:
            fallback.append(text)
            continue
        if best_dt is None or parsed > best_dt:
            best_dt = parsed
            best_text = text
    if best_text:
        return best_text
    return max(fallback) if fallback else ""


def _newer_same_cwd_sessions(
    *,
    metadata: dict[str, Any],
    out_dir: Path,
    session_updated_at: str,
    linked_child_sessions: list[dict[str, str]],
) -> list[dict[str, Any]]:
    cwd = _normalize_freshness_path(_string(metadata.get("cwd")))
    session_id = _string(metadata.get("session_id"))
    if not cwd or not session_id or not session_updated_at:
        return []

    child_ids = {
        _string(child.get("child_session_id"))
        for child in linked_child_sessions
        if _string(child.get("child_session_id"))
    }
    try:
        entries = load_index(out_dir)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

    matches: list[dict[str, Any]] = []
    for entry in entries:
        candidate_id = _string(entry.get("session_id"))
        if not candidate_id or candidate_id == session_id or candidate_id in child_ids:
            continue
        if _normalize_freshness_path(_string(entry.get("cwd"))) != cwd:
            continue
        candidate_updated_at = _string(entry.get("updated_at"))
        if not _timestamp_after(candidate_updated_at, session_updated_at):
            continue
        matches.append(
            {
                "session_id": candidate_id,
                "title": _string(entry.get("title")),
                "updated_at": candidate_updated_at,
            }
        )

    return sorted(
        matches,
        key=lambda item: (_string(item.get("updated_at")), _string(item.get("session_id"))),
        reverse=True,
    )[:3]


def _normalize_freshness_path(path: str) -> str:
    if not path:
        return ""
    try:
        return Path(path).expanduser().resolve(strict=False).as_posix()
    except OSError:
        return path.strip().replace("\\", "/").rstrip("/")


def _timestamp_after_with_tolerance(
    candidate: str,
    reference: str,
    *,
    tolerance: timedelta,
) -> bool:
    candidate_dt = _parse_iso_timestamp(candidate)
    reference_dt = _parse_iso_timestamp(reference)
    if candidate_dt is None or reference_dt is None:
        return False
    return candidate_dt - reference_dt > tolerance


def _parse_iso_timestamp(text: str) -> datetime | None:
    value = _string(text)
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
