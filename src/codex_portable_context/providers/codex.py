"""Codex provider adapter."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from codex_portable_context.core.parsing import (
    ParsedSession,
    load_source_session_index,
    parse_session_file,
)
from codex_portable_context.providers.base import (
    ProviderCapabilities,
    ProviderSessionDescriptor,
    ProviderSourceContext,
)


class CodexSessionAdapter:
    """Provider adapter for the current Codex session layout."""

    provider_id = "codex"

    def default_home_dir(self) -> Path:
        raw_path = os.environ.get("CODEX_HOME")
        if raw_path:
            return Path(raw_path).expanduser()
        return Path.home() / ".codex"

    def default_source_dir(self, home_dir: Path) -> Path:
        return home_dir / "sessions"

    def iter_session_files(self, source_dir: Path) -> Iterator[Path]:
        yield from sorted(path for path in source_dir.rglob("rollout-*.jsonl") if path.is_file())

    def build_source_context(self, home_dir: Path) -> ProviderSourceContext:
        return ProviderSourceContext(native_index_by_session_id=load_source_session_index(home_dir))

    def describe_session(
        self,
        *,
        parsed: ParsedSession,
        source_context: ProviderSourceContext,
        session_file: Path,
    ) -> ProviderSessionDescriptor:
        source_index = source_context.native_index_by_session_id or {}
        source_meta = source_index.get(parsed.session_id, {})
        thread_name = _string_value(source_meta.get("thread_name"))
        updated_at = _best_updated_at(
            _string_value(source_meta.get("updated_at")),
            parsed,
            session_file,
        )
        return ProviderSessionDescriptor(
            provider=parsed.provider,
            provider_session_id=parsed.provider_session_id,
            session_id=parsed.session_id,
            source_file=parsed.source_file,
            source_relpath=parsed.source_relpath,
            thread_name=thread_name,
            updated_at=updated_at,
        )

    def parse_session_file(self, path: Path, source_dir: Path) -> ParsedSession:
        return parse_session_file(path, source_dir, provider_id=self.provider_id)

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_tools=True,
            supports_reader_html=True,
            supports_handoff_source_enrichment=True,
            supports_context_sections=True,
            supports_redaction_source_context=True,
            supports_latest_selection=True,
        )


def _file_updated_at(path: Path) -> str:
    timestamp = datetime.fromtimestamp(path.stat().st_mtime_ns / 1_000_000_000, tz=UTC)
    return timestamp.isoformat().replace("+00:00", "Z")


def _best_updated_at(
    indexed_updated_at: str | None,
    parsed: ParsedSession,
    session_file: Path,
) -> str:
    candidates = [indexed_updated_at, _best_parsed_timestamp(parsed)]
    timestamps = [candidate for candidate in candidates if candidate]
    if timestamps:
        return max(timestamps)
    return _file_updated_at(session_file)


def _best_parsed_timestamp(parsed: ParsedSession) -> str | None:
    candidates = [parsed.session_timestamp]
    candidates.extend(block.timestamp for block in parsed.context_entries)
    candidates.extend(block.timestamp for block in parsed.conversation_entries)
    candidates.extend(block.timestamp for block in parsed.notable_events)
    timestamps = [candidate for candidate in candidates if candidate]
    return max(timestamps) if timestamps else None


def _string_value(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
