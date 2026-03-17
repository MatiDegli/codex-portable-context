"""Claude Code provider adapter."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from codex_portable_context.core.parsing import (
    ParsedSession,
    RenderBlock,
    load_jsonl_objects,
)
from codex_portable_context.core.source_paths import source_relpath
from codex_portable_context.providers.base import (
    ProviderCapabilities,
    ProviderSessionDescriptor,
    ProviderSourceContext,
)


class ClaudeCodeSessionAdapter:
    """Provider adapter for the first conservative Claude Code source layout."""

    provider_id = "claude-code"

    def default_home_dir(self) -> Path:
        return Path.home() / ".claude"

    def default_source_dir(self, home_dir: Path) -> Path:
        return home_dir / "projects"

    def iter_session_files(self, source_dir: Path) -> Iterator[Path]:
        yield from sorted(
            path
            for path in source_dir.rglob("*.jsonl")
            if path.is_file() and _is_primary_session_file(path, source_dir)
        )

    def build_source_context(self, home_dir: Path) -> ProviderSourceContext:
        return ProviderSourceContext()

    def describe_session(
        self,
        *,
        parsed: ParsedSession,
        source_context: ProviderSourceContext,
        session_file: Path,
    ) -> ProviderSessionDescriptor:
        del source_context
        return ProviderSessionDescriptor(
            provider=parsed.provider,
            provider_session_id=parsed.provider_session_id,
            session_id=parsed.session_id,
            source_file=parsed.source_file,
            source_relpath=parsed.source_relpath,
            updated_at=_best_parsed_timestamp(parsed) or _file_updated_at(session_file),
        )

    def parse_session_file(self, path: Path, source_dir: Path) -> ParsedSession:
        records = load_jsonl_objects(path)
        contexts: list[RenderBlock] = []
        conversation: list[RenderBlock] = []
        notable_events: list[RenderBlock] = []
        user_messages: list[str] = []
        assistant_messages: list[str] = []

        session_id = ""
        session_timestamp: str | None = None
        cwd: str | None = None
        model_provider: str | None = None

        for record in records:
            timestamp = _string_value(
                record.get("timestamp")
                or record.get("createdAt")
                or record.get("updatedAt")
            )
            if session_timestamp is None and timestamp:
                session_timestamp = timestamp

            session_id = (
                session_id
                or _string_value(record.get("sessionId"))
                or _string_value(record.get("session_id"))
                or ""
            )
            cwd = cwd or _string_value(record.get("cwd"))

            model_name = _string_value(record.get("model"))
            if model_provider is None and model_name and "claude" in model_name.lower():
                model_provider = "anthropic"

            role = _record_role(record)
            text = _message_text(record)

            if role in {"system", "developer"} and text:
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

            if role == "user" and text:
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

            if role == "assistant" and text:
                assistant_messages.append(text)
                conversation.append(
                    RenderBlock(
                        kind="assistant",
                        label="Assistant",
                        role="assistant",
                        timestamp=timestamp,
                        text=text,
                    )
                )
                continue

            event_type = _string_value(record.get("type")) or "record"
            if event_type in {"file-history-snapshot"}:
                notable_events.append(
                    RenderBlock(
                        kind="event",
                        label=f"Event ({event_type})",
                        timestamp=timestamp,
                        text=_json_text(record),
                    )
                )

        resolved_session_id = session_id or path.stem
        return ParsedSession(
            provider=self.provider_id,
            provider_session_id=resolved_session_id,
            source_file=path.resolve(),
            source_relpath=source_relpath(path, source_dir),
            session_id=resolved_session_id,
            session_timestamp=session_timestamp,
            cwd=cwd,
            originator=None,
            source=self.provider_id,
            model_provider=model_provider,
            cli_version=None,
            context_entries=contexts,
            conversation_entries=conversation,
            notable_events=notable_events,
            user_messages=user_messages,
            assistant_messages=assistant_messages,
            event_count=len(records),
            context_entry_count=len(contexts),
            user_message_count=len(user_messages),
            assistant_message_count=len(assistant_messages),
            tool_call_count=0,
            tool_output_count=0,
            notable_event_count=len(notable_events),
        )

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_tools=False,
            supports_reader_html=True,
            supports_handoff_source_enrichment=True,
            supports_context_sections=True,
            supports_redaction_source_context=True,
            supports_latest_selection=True,
        )


def _is_primary_session_file(path: Path, source_dir: Path) -> bool:
    try:
        rel_parts = path.relative_to(source_dir).parts
    except ValueError:
        return False
    return len(rel_parts) == 2


def _record_role(record: dict[str, object]) -> str | None:
    explicit_role = _string_value(record.get("role"))
    if explicit_role:
        return explicit_role.lower()

    record_type = (_string_value(record.get("type")) or "").lower()
    if record_type in {"user", "assistant", "system", "developer"}:
        return record_type
    if record_type == "message":
        return explicit_role.lower() if explicit_role else None
    return None


def _message_text(record: dict[str, object]) -> str:
    message = record.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if content is not None:
            return _content_text(content)
    if message is not None:
        return _content_text(message)

    content = record.get("content")
    if content is not None:
        return _content_text(content)
    return ""


def _content_text(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = [_content_text(item) for item in value]
        return "\n\n".join(part for part in parts if part)
    if isinstance(value, dict):
        for key in ("text", "content", "value"):
            text = _content_text(value.get(key))
            if text:
                return text
    return ""


def _best_parsed_timestamp(parsed: ParsedSession) -> str | None:
    candidates = [parsed.session_timestamp]
    candidates.extend(block.timestamp for block in parsed.context_entries)
    candidates.extend(block.timestamp for block in parsed.conversation_entries)
    candidates.extend(block.timestamp for block in parsed.notable_events)
    timestamps = [candidate for candidate in candidates if candidate]
    return max(timestamps) if timestamps else None


def _file_updated_at(path: Path) -> str:
    timestamp = datetime.fromtimestamp(path.stat().st_mtime_ns / 1_000_000_000, tz=UTC)
    return timestamp.isoformat().replace("+00:00", "Z")


def _json_text(value: object) -> str:
    import json

    return json.dumps(value, indent=2, ensure_ascii=False)


def _string_value(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
