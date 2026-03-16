"""Extractive handoff bundle helpers for derived mirrors."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from .discovery import mirror_layout
from .index import MirrorEntry, entry_path
from .markdown import pretty_timestamp
from .parsing import ParsedSession, RenderBlock, parse_session_file
from .redaction import RedactionContext, redact_text


@dataclass(frozen=True, slots=True)
class HandoffResult:
    """Written handoff artifact paths."""

    session_id: str
    markdown_path: Path
    json_path: Path


def generate_handoff(entry: MirrorEntry, out_dir: Path | None = None) -> HandoffResult:
    """Write an extractive handoff bundle for one derived mirror entry."""

    layout = mirror_layout(out_dir)
    layout.handoffs_dir.mkdir(parents=True, exist_ok=True)

    session_id = str(entry["session_id"])
    metadata_path = entry_path(entry, "metadata", layout.out_dir)
    markdown_path = entry_path(entry, "markdown", layout.out_dir)
    reader_relpath = str(
        entry.get("reader_relpath") or layout.reader_relpath(session_id)
    )

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    transcript_text = markdown_path.read_text(encoding="utf-8")

    parsed = _load_source_session(metadata)
    handoff = _build_handoff_payload(
        metadata=metadata,
        transcript_text=transcript_text,
        parsed=parsed,
        reader_relpath=reader_relpath,
    )

    handoff_json_path = layout.handoff_json_path(session_id)
    handoff_markdown_path = layout.handoff_markdown_path(session_id)
    handoff_json_path.write_text(
        json.dumps(handoff, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    handoff_markdown_path.write_text(
        render_handoff_markdown(handoff),
        encoding="utf-8",
    )

    return HandoffResult(
        session_id=session_id,
        markdown_path=handoff_markdown_path,
        json_path=handoff_json_path,
    )


def render_handoff_markdown(handoff: dict[str, Any]) -> str:
    """Render a readable handoff Markdown document."""

    session = _as_dict(handoff.get("session"))
    artifacts = _as_dict(handoff.get("artifacts"))
    source = _as_dict(handoff.get("source_availability"))
    template = _as_dict(handoff.get("operator_note_template"))
    recent_window = _as_list(handoff.get("recent_window"))
    recent_events = _as_list(handoff.get("recent_notable_events"))
    recent_tools = _as_list(handoff.get("recent_tool_activity"))
    transcript_link = _handoff_relpath(_string(artifacts.get("markdown_relpath")))
    metadata_link = _handoff_relpath(_string(artifacts.get("metadata_relpath")))
    reader_link = _handoff_relpath(_string(artifacts.get("reader_relpath")))
    updated_at = pretty_timestamp(
        _string(handoff.get("updated_at")) or _string(handoff.get("session_timestamp"))
    )
    generated_at = pretty_timestamp(_string(handoff.get("generated_at")))

    lines: list[str] = [
        f"# Handoff: {session.get('title') or handoff.get('session_id')}",
        "",
        (
            "This handoff bundle is extractive and local-first. "
            "It does not resume or write back into Codex state."
        ),
        "",
        "## Snapshot",
        "",
        f"- Session ID: `{handoff.get('session_id')}`",
        f"- Updated: `{updated_at}`",
        f"- Exported At: `{generated_at}`",
        f"- Redacted: `{'yes' if handoff.get('redacted') else 'no'}`",
        f"- Source session available locally: `{'yes' if source.get('available') else 'no'}`",
        "",
        f"- Started with: {session.get('preview') or 'n/a'}",
        f"- Last user message: {session.get('last_user_message') or 'n/a'}",
        f"- Latest assistant reply: {session.get('last_assistant_message') or 'n/a'}",
        f"- Activity: {session.get('activity') or 'n/a'}",
        f"- Environment: {session.get('environment') or 'n/a'}",
        "",
        "## Artifacts",
        "",
        f"- Transcript: [{artifacts.get('markdown_relpath')}]({transcript_link})",
        f"- Metadata: [{artifacts.get('metadata_relpath')}]({metadata_link})",
        f"- Reader: [{artifacts.get('reader_relpath')}]({reader_link})",
        "",
        "## Operator Note Template",
        "",
        f"- What matters now: {template.get('what_matters_now')}",
        f"- Next step: {template.get('next_step')}",
        f"- Known risks: {template.get('known_risks')}",
        "",
    ]

    excerpt = _string(handoff.get("transcript_excerpt"))
    if excerpt:
        lines.extend(
            [
                "## Transcript Excerpt",
                "",
                excerpt,
                "",
            ]
        )

    if recent_window:
        lines.extend(["## Recent Conversation Window", ""])
        for item in recent_window:
            block = _as_dict(item)
            lines.extend(
                [
                    f"### {block.get('label')}",
                    "",
                    f"- Kind: `{block.get('kind')}`",
                    f"- Timestamp: `{pretty_timestamp(_string(block.get('timestamp')) )}`",
                    block.get("text") or "_No text available._",
                    "",
                ]
            )

    if recent_events:
        lines.extend(["## Recent Notable Events", ""])
        for item in recent_events:
            event = _as_dict(item)
            timestamp = pretty_timestamp(_string(event.get("timestamp")))
            line = f"- `{timestamp}` {event.get('label')}: {event.get('text')}"
            lines.extend(
                [
                    line,
                ]
            )
        lines.append("")

    if recent_tools:
        lines.extend(["## Recent Tool Activity", ""])
        for item in recent_tools:
            tool = _as_dict(item)
            lines.extend(
                [
                    f"### {tool.get('label')}",
                    "",
                    f"- Timestamp: `{pretty_timestamp(_string(tool.get('timestamp')) )}`",
                    f"- Tool: `{tool.get('tool_name') or 'unknown'}`",
                    tool.get("text") or "_No text available._",
                    "",
                ]
            )

    return "\n".join(lines)


def _build_handoff_payload(
    *,
    metadata: dict[str, Any],
    transcript_text: str,
    parsed: ParsedSession | None,
    reader_relpath: str,
) -> dict[str, Any]:
    summary = _as_dict(metadata.get("summary"))
    redacted = bool(metadata.get("redacted"))
    redaction_context = RedactionContext.detect()

    recent_window = (
        [
            _render_block_payload(block, redacted=redacted, context=redaction_context)
            for block in parsed.conversation_entries[-8:]
        ]
        if parsed
        else []
    )
    recent_events = (
        [
            _render_block_payload(block, redacted=redacted, context=redaction_context)
            for block in parsed.notable_events[-5:]
        ]
        if parsed
        else []
    )
    recent_tools = (
        [
            _render_block_payload(block, redacted=redacted, context=redaction_context)
            for block in parsed.conversation_entries
            if block.kind == "tool_call"
        ][-5:]
        if parsed
        else []
    )

    return {
        "handoff_schema_version": 1,
        "generated_at": _iso_now(),
        "session_id": metadata.get("session_id"),
        "title": metadata.get("title"),
        "updated_at": metadata.get("updated_at"),
        "session_timestamp": metadata.get("session_timestamp"),
        "redacted": redacted,
        "session": {
            "title": metadata.get("title"),
            "preview": summary.get("preview", ""),
            "first_user_message": summary.get("first_user_message", ""),
            "last_user_message": summary.get("last_user_message", ""),
            "last_assistant_message": summary.get("last_assistant_message", ""),
            "activity": summary.get("activity", ""),
            "environment": summary.get("environment", ""),
            "detail_line": summary.get("detail_line", ""),
            "one_line": summary.get("one_line", ""),
        },
        "artifacts": {
            "metadata_relpath": str(metadata.get("metadata_relpath") or ""),
            "markdown_relpath": str(metadata.get("markdown_relpath") or ""),
            "reader_relpath": reader_relpath,
        },
        "source_availability": {
            "available": parsed is not None,
            "exact_recent_window": parsed is not None,
            "source_file": metadata.get("source_file"),
            "note": (
                "Recent window and tool activity were extracted from the local source session."
                if parsed is not None
                else "Only derived mirror data was available locally."
            ),
        },
        "recent_window": recent_window,
        "recent_notable_events": recent_events,
        "recent_tool_activity": recent_tools,
        "operator_note_template": {
            "what_matters_now": "",
            "next_step": "",
            "known_risks": "",
        },
        "transcript_excerpt": _excerpt_text(transcript_text, limit=900),
    }


def _load_source_session(metadata: dict[str, Any]) -> ParsedSession | None:
    source_file_value = metadata.get("source_file")
    source_relpath_value = metadata.get("source_relpath")
    if not isinstance(source_file_value, str) or not source_file_value.strip():
        return None
    if not isinstance(source_relpath_value, str) or not source_relpath_value.strip():
        return None

    source_file = Path(source_file_value).expanduser()
    if not source_file.is_file():
        return None

    source_dir = _infer_source_dir(source_file.resolve(), source_relpath_value)
    return parse_session_file(source_file.resolve(), source_dir)


def _infer_source_dir(source_file: Path, source_relpath: str) -> Path:
    current = source_file
    for _ in PurePosixPath(source_relpath).parts:
        current = current.parent
    return current


def _render_block_payload(
    block: RenderBlock,
    *,
    redacted: bool,
    context: RedactionContext,
) -> dict[str, Any]:
    text = block.text
    if redacted:
        text = redact_text(text, context).text
    return {
        "kind": block.kind,
        "label": block.label,
        "timestamp": block.timestamp,
        "role": block.role,
        "tool_name": block.tool_name,
        "call_id": block.call_id,
        "text": _excerpt_text(text, limit=600),
    }


def _excerpt_text(text: str, *, limit: int) -> str:
    stripped = text.strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[: max(0, limit - 3)].rstrip() + "..."


def _iso_now() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string(value: Any) -> str:
    return str(value) if value is not None else ""


def _handoff_relpath(path: str) -> str:
    if not path:
        return ""
    return "../" + path.lstrip("./")
