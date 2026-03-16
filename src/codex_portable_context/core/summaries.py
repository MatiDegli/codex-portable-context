"""Mechanical summary helpers for the Python v2 mirror exporter."""

from __future__ import annotations

from pathlib import Path

from .parsing import ParsedSession


def derive_session_title(parsed: ParsedSession, thread_name: str | None) -> str:
    """Derive the exported session title."""

    if thread_name:
        return thread_name

    first_user_message = parsed.user_messages[0] if parsed.user_messages else ""
    if first_user_message:
        return ellipsize(single_line(first_user_message), limit=96)

    return f"Session {parsed.session_id}"


def build_summary(parsed: ParsedSession) -> dict[str, str]:
    """Build the mechanical summary object for one exported session."""

    first_user_message = (
        ellipsize(single_line(parsed.user_messages[0]), limit=160)
        if parsed.user_messages
        else ""
    )
    last_user_message = (
        ellipsize(single_line(parsed.user_messages[-1]), limit=160)
        if parsed.user_messages
        else ""
    )
    last_assistant_message = (
        ellipsize(single_line(parsed.assistant_messages[-1]), limit=160)
        if parsed.assistant_messages
        else ""
    )

    activity = (
        f"{parsed.user_message_count} user messages, "
        f"{parsed.assistant_message_count} assistant messages | "
        f"{parsed.tool_call_count} tool calls, "
        f"{parsed.tool_output_count} tool outputs | "
        f"{parsed.notable_event_count} notable events"
    )

    environment_parts: list[str] = []
    if parsed.cwd:
        environment_parts.append(f"cwd: {Path(parsed.cwd).name or parsed.cwd}")
    if parsed.source:
        environment_parts.append(f"source: {parsed.source}")
    if parsed.originator:
        environment_parts.append(f"originator: {parsed.originator}")
    environment = ", ".join(environment_parts)

    detail_parts = [activity]
    if environment:
        detail_parts.append(environment)
    detail_line = " | ".join(detail_parts)

    preview = first_user_message
    one_line = f"Started with: {preview}" if preview else "Started with: n/a"

    return {
        "preview": preview,
        "first_user_message": first_user_message,
        "last_user_message": last_user_message,
        "last_assistant_message": last_assistant_message,
        "activity": activity,
        "environment": environment,
        "detail_line": detail_line,
        "one_line": one_line,
    }


def single_line(text: str) -> str:
    """Collapse whitespace for short summary views."""

    return " ".join(text.split())


def ellipsize(text: str, *, limit: int) -> str:
    """Trim long summary text to a fixed limit."""

    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."
