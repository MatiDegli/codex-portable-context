"""Codex provider adapter."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from codex_portable_context.core.discovery import iter_session_files
from codex_portable_context.core.parsing import (
    JsonObject,
    ParsedSession,
    load_source_session_index,
    parse_session_file,
)
from codex_portable_context.providers.base import ProviderCapabilities, ProviderSessionHints


class CodexSessionAdapter:
    """Provider adapter for the current Codex session layout."""

    provider_id = "codex"

    def iter_session_files(self, source_dir: Path) -> Iterator[Path]:
        return iter_session_files(source_dir)

    def load_source_index(self, home_dir: Path) -> dict[str, JsonObject]:
        return load_source_session_index(home_dir)

    def session_hints(
        self,
        *,
        parsed: ParsedSession,
        source_index: dict[str, JsonObject],
        session_file: Path,
    ) -> ProviderSessionHints:
        source_meta = source_index.get(parsed.session_id, {})
        thread_name = _string_value(source_meta.get("thread_name"))
        updated_at = _string_value(source_meta.get("updated_at")) or _file_updated_at(session_file)
        return ProviderSessionHints(thread_name=thread_name, updated_at=updated_at)

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


def _string_value(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
