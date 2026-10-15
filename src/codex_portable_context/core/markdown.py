"""Markdown rendering helpers for the Python v2 mirror exporter."""

from __future__ import annotations

from typing import Any

from .contract import LANDING_MARKER, MARKDOWN_FILTER_RULES
from .parsing import ParsedSession, RenderBlock


def pretty_timestamp(value: str | None) -> str:
    """Render a readable timestamp string without inventing new values."""

    if not value:
        return "unknown"
    cleaned = value.replace("T", " ")
    if "." in cleaned and cleaned.endswith("Z"):
        cleaned = cleaned.split(".", maxsplit=1)[0] + "Z"
    return cleaned


def render_session_markdown(
    *,
    parsed: ParsedSession,
    title: str,
    thread_name: str | None,
    updated_at: str | None,
    export_profile: str,
    summary: dict[str, str],
    include_context: bool,
    include_tools: bool,
    include_events: bool,
) -> str:
    """Render one exported session transcript."""

    lines: list[str] = [f"# {title}", ""]

    lines.extend(
        [
            "## Metadata",
            "",
            f"- Session ID: `{parsed.session_id}`",
        ]
    )
    if thread_name:
        lines.append(f"- Thread Name: `{thread_name}`")
    if parsed.session_timestamp:
        lines.append(f"- Session Timestamp: `{pretty_timestamp(parsed.session_timestamp)}`")
    if updated_at:
        lines.append(f"- Updated At: `{pretty_timestamp(updated_at)}`")
    if parsed.cwd:
        lines.append(f"- CWD: `{parsed.cwd}`")
    lines.append("")

    lines.extend(
        [
            "## Session Snapshot",
            "",
            f"- Started with: {summary['preview'] or 'n/a'}",
            f"- Latest assistant reply: {summary['last_assistant_message'] or 'n/a'}",
            f"- Activity: {summary['activity'] or 'n/a'}",
            f"- Environment: {summary['environment'] or 'n/a'}",
            "",
            "## Export Notes",
            "",
            f"- Export profile: `{export_profile}`",
            (
                "- This Markdown omits routine `token_count` and "
                "`turn_context` records to reduce noise."
            ),
            "- Raw source session files remain untouched and are the authoritative input.",
            "",
        ]
    )

    if include_context and parsed.context_entries:
        lines.extend(["## Session Context", ""])
        lines.extend(_render_blocks(parsed.context_entries))

    lines.extend(["## Conversation", ""])
    conversation = [
        block
        for block in parsed.conversation_entries
        if include_tools or block.kind not in {"tool_call", "tool_output"}
    ]
    if conversation:
        lines.extend(_render_blocks(conversation, code_block_kinds={"tool_call", "tool_output"}))
    else:
        lines.extend(["_No conversation entries matched the selected export profile._", ""])

    if include_events and parsed.notable_events:
        lines.extend(["## Notable Events", ""])
        lines.extend(_render_blocks(parsed.notable_events, code_block_kinds={"event"}))

    lines.extend(["## Markdown Filter Rules", ""])
    for rule in MARKDOWN_FILTER_RULES:
        lines.append(f"- {rule}")
    lines.append("")

    return "\n".join(lines)


def render_landing(
    *,
    entries: list[dict[str, Any]],
    exported_at: str,
    redacted_export: bool,
) -> str:
    """Render the mirror landing page from derived index entries only."""

    lines: list[str] = [
        LANDING_MARKER,
        "# Codex Portable Context Mirror",
        "",
        "This directory is a derived read-only mirror generated from local Codex session exports.",
        (
            "Use the links below for reading and transport. "
            "This is not a writable Codex state directory."
        ),
        "",
        "## Mirror Summary",
        "",
        f"- Exported at: `{pretty_timestamp(exported_at)}`",
        f"- Sessions: `{len(entries)}`",
        (
            f"- Latest session update: "
            f"`{pretty_timestamp(_entry_sort_timestamp(entries[0]) if entries else None)}`"
        ),
        f"- Redacted export: `{'yes' if redacted_export else 'no'}`",
        "- Session index: [sessions-index.jsonl](sessions-index.jsonl)",
        "- Browser reader: [index.html](index.html)",
        "",
    ]

    if entries:
        latest = entries[0]
        lines.extend(
            [
                "## Start Here",
                "",
                (
                    "- Open the latest transcript for the readable conversation view: "
                    f"[{latest['markdown_relpath']}]({latest['markdown_relpath']})"
                ),
                (
                    "- Open the latest metadata for structured fields and redaction info: "
                    f"[{latest['metadata_relpath']}]({latest['metadata_relpath']})"
                ),
                "- Use `sessions-index.jsonl` for scripting and helper CLIs.",
                "",
            ]
        )

    lines.extend(["## Sessions", ""])
    if not entries:
        lines.extend(["_No sessions are currently exported in this mirror._", ""])
        return "\n".join(lines)

    for entry in entries:
        summary = entry.get("summary")
        summary_dict = summary if isinstance(summary, dict) else {}
        lines.extend(
            [
                f"### {entry.get('title') or 'Untitled Session'}",
                "",
                f"- Session ID: `{entry['session_id']}`",
                f"- Updated: `{pretty_timestamp(_entry_sort_timestamp(entry))}`",
                f"- Transcript: [{entry['markdown_relpath']}]({entry['markdown_relpath']})",
                f"- Metadata: [{entry['metadata_relpath']}]({entry['metadata_relpath']})",
            ]
        )
        if summary_dict.get("preview"):
            lines.append(f"- Started with: {summary_dict['preview']}")
        if summary_dict.get("last_assistant_message"):
            lines.append(f"- Latest assistant reply: {summary_dict['last_assistant_message']}")
        if summary_dict.get("activity"):
            lines.append(f"- Activity: {summary_dict['activity']}")
        if summary_dict.get("environment"):
            lines.append(f"- Environment: {summary_dict['environment']}")
        lines.append("")

    return "\n".join(lines)


def _render_blocks(
    blocks: list[RenderBlock],
    *,
    code_block_kinds: set[str] | None = None,
) -> list[str]:
    lines: list[str] = []
    code_block_kinds = code_block_kinds or set()
    counters: dict[str, int] = {}

    for block in blocks:
        counters[block.kind] = counters.get(block.kind, 0) + 1
        number = counters[block.kind]
        heading = f"{block.label.split(' (', maxsplit=1)[0]} {number}{_label_suffix(block.label)}"
        lines.append(f"### {heading}")
        lines.append("")
        lines.append(f"Timestamp: `{pretty_timestamp(block.timestamp)}`")
        lines.append("")
        if block.kind in code_block_kinds:
            lines.append("```text")
            lines.append(block.text)
            lines.append("```")
        else:
            lines.append(block.text)
        lines.append("")
    return lines


def _label_suffix(label: str) -> str:
    if " (" not in label:
        return ""
    return label[label.index(" (") :]


def _entry_sort_timestamp(entry: dict[str, Any]) -> str | None:
    for key in ("updated_at", "session_timestamp", "exported_at"):
        value = entry.get(key)
        if value:
            return str(value)
    return None
