"""Raw session parsing helpers for the Python v2 mirror exporter."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .source_paths import source_relpath

JsonObject = dict[str, Any]

NOTABLE_EVENT_TYPES = {
    "task_started",
    "task_complete",
    "context_compacted",
    "turn_aborted",
    "thread_rolled_back",
    "item_completed",
}

TOOL_CALL_TYPES = {
    "function_call",
    "custom_tool_call",
    "web_search_call",
}

TOOL_OUTPUT_TYPES = {
    "function_call_output",
    "custom_tool_call_output",
}


@dataclass(slots=True)
class RenderBlock:
    """One readable derived block for context, conversation, or events."""

    kind: str
    label: str
    timestamp: str | None
    text: str
    role: str | None = None
    tool_name: str | None = None
    call_id: str | None = None


@dataclass(slots=True)
class ParsedSession:
    """Structured representation of one raw provider session file."""

    provider: str
    provider_session_id: str
    source_file: Path
    source_relpath: str
    session_id: str
    session_timestamp: str | None
    cwd: str | None
    originator: str | None
    source: str | None
    model_provider: str | None
    cli_version: str | None
    context_entries: list[RenderBlock]
    conversation_entries: list[RenderBlock]
    notable_events: list[RenderBlock]
    user_messages: list[str]
    assistant_messages: list[str]
    event_count: int
    context_entry_count: int
    user_message_count: int
    assistant_message_count: int
    tool_call_count: int
    tool_output_count: int
    notable_event_count: int


def load_jsonl_objects(path: Path) -> list[JsonObject]:
    """Load raw JSONL objects from a file."""

    records: list[JsonObject] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            records.append(json.loads(stripped))
    return records


def load_source_session_index(codex_home: Path) -> dict[str, JsonObject]:
    """Load the optional raw Codex session index keyed by session id."""

    index_path = codex_home / "session_index.jsonl"
    if not index_path.is_file():
        return {}

    index_entries: dict[str, JsonObject] = {}
    for entry in load_jsonl_objects(index_path):
        session_id = entry.get("id")
        if session_id:
            index_entries[str(session_id)] = entry
    return index_entries


def parse_session_file(
    path: Path,
    source_dir: Path,
    *,
    provider_id: str = "codex",
) -> ParsedSession:
    """Parse one raw provider session file into structured derived data."""

    records = load_jsonl_objects(path)
    session_meta: JsonObject = {}
    contexts: list[RenderBlock] = []
    conversation: list[RenderBlock] = []
    notable_events: list[RenderBlock] = []
    user_messages: list[str] = []
    assistant_messages: list[str] = []
    call_name_by_id: dict[str, str] = {}

    for record in records:
        record_type = str(record.get("type") or "")
        timestamp = _string_value(record.get("timestamp"))
        payload = record.get("payload")
        payload_dict = payload if isinstance(payload, dict) else {}
        payload_type = str(payload_dict.get("type") or "")

        if record_type == "session_meta":
            if session_meta:
                continue
            session_meta = payload_dict
            continue

        if record_type == "response_item" and payload_type == "message":
            role = str(payload_dict.get("role") or "")
            text = _message_content_text(payload_dict.get("content"))
            if role in {"developer", "user"} and text:
                contexts.append(
                    RenderBlock(
                        kind="context",
                        label=f"Context ({role})",
                        role=role,
                        timestamp=timestamp,
                        text=text,
                    )
                )
            continue

        if record_type == "event_msg" and payload_type == "user_message":
            text = _normalize_text(payload_dict.get("message"))
            if text:
                user_messages.append(text)
                conversation.append(
                    RenderBlock(
                        kind="user",
                        label="User",
                        role="user",
                        timestamp=timestamp,
                        text=text,
                    )
                )
            continue

        if record_type == "event_msg" and payload_type == "agent_message":
            text = _normalize_text(payload_dict.get("message"))
            if text:
                assistant_messages.append(text)
                phase = _string_value(payload_dict.get("phase"))
                label = "Assistant"
                if phase:
                    label = f"Assistant ({phase})"
                conversation.append(
                    RenderBlock(
                        kind="assistant",
                        label=label,
                        role="assistant",
                        timestamp=timestamp,
                        text=text,
                    )
                )
            continue

        if record_type == "response_item" and payload_type in TOOL_CALL_TYPES:
            tool_name = _string_value(payload_dict.get("name")) or payload_type
            call_id = _string_value(payload_dict.get("call_id"))
            if call_id:
                call_name_by_id[call_id] = tool_name
            tool_text = _tool_call_text(payload_dict)
            conversation.append(
                RenderBlock(
                    kind="tool_call",
                    label=f"Tool Call ({tool_name})",
                    timestamp=timestamp,
                    text=tool_text,
                    tool_name=tool_name,
                    call_id=call_id,
                )
            )
            continue

        if record_type == "response_item" and payload_type in TOOL_OUTPUT_TYPES:
            call_id = _string_value(payload_dict.get("call_id"))
            tool_name = call_name_by_id.get(call_id or "", payload_type)
            tool_text = _tool_output_text(payload_dict)
            conversation.append(
                RenderBlock(
                    kind="tool_output",
                    label=f"Tool Output ({tool_name})",
                    timestamp=timestamp,
                    text=tool_text,
                    tool_name=tool_name,
                    call_id=call_id,
                )
            )
            continue

        if record_type == "event_msg" and payload_type in NOTABLE_EVENT_TYPES:
            event_text = _json_text(_without_keys(payload_dict, {"type"}))
            notable_events.append(
                RenderBlock(
                    kind="event",
                    label=f"Event ({payload_type})",
                    timestamp=timestamp,
                    text=event_text,
                )
            )

    session_id = _string_value(session_meta.get("id")) or path.name.removesuffix(".jsonl")

    return ParsedSession(
        provider=provider_id,
        provider_session_id=session_id,
        source_file=path.resolve(),
        source_relpath=source_relpath(path, source_dir),
        session_id=session_id,
        session_timestamp=_string_value(session_meta.get("timestamp")),
        cwd=_string_value(session_meta.get("cwd")),
        originator=_string_value(session_meta.get("originator")),
        source=_string_value(session_meta.get("source")),
        model_provider=_string_value(session_meta.get("model_provider")),
        cli_version=_string_value(session_meta.get("cli_version")),
        context_entries=contexts,
        conversation_entries=conversation,
        notable_events=notable_events,
        user_messages=user_messages,
        assistant_messages=assistant_messages,
        event_count=len(records),
        context_entry_count=len(contexts),
        user_message_count=len(user_messages),
        assistant_message_count=len(assistant_messages),
        tool_call_count=sum(1 for item in conversation if item.kind == "tool_call"),
        tool_output_count=sum(1 for item in conversation if item.kind == "tool_output"),
        notable_event_count=len(notable_events),
    )


def _message_content_text(content: object) -> str:
    if not isinstance(content, list):
        return ""

    chunks: list[str] = []
    for part in content:
        if not isinstance(part, dict):
            continue
        text = _normalize_text(part.get("text"))
        if text:
            chunks.append(text)
    return "\n\n".join(chunks)


def _tool_call_text(payload: JsonObject) -> str:
    arguments = payload.get("arguments")
    input_value = payload.get("input")
    body = arguments if arguments is not None else input_value
    if body is None:
        body = _without_keys(payload, {"type", "name", "call_id", "status"})
    return _json_or_text(body)


def _tool_output_text(payload: JsonObject) -> str:
    output = payload.get("output")
    if output is None:
        output = _without_keys(payload, {"type", "call_id"})
    return _json_or_text(output)


def _json_or_text(value: object) -> str:
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return ""
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return stripped
        return _json_text(parsed)
    if isinstance(value, dict | list):
        return _json_text(value)
    if value is None:
        return ""
    return str(value)


def _json_text(value: object) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False)


def _without_keys(payload: JsonObject, keys: set[str]) -> JsonObject:
    return {key: value for key, value in payload.items() if key not in keys}


def _normalize_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _string_value(value: object) -> str | None:
    text = _normalize_text(value)
    return text or None
