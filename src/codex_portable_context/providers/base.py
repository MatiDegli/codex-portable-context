"""Small provider adapter interface for raw session sources."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from codex_portable_context.core.parsing import JsonObject, ParsedSession


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    """Small capability set that lets the core adapt provider differences safely."""

    supports_tools: bool
    supports_reader_html: bool
    supports_handoff_source_enrichment: bool
    supports_context_sections: bool
    supports_redaction_source_context: bool
    supports_latest_selection: bool


class SessionProviderAdapter(Protocol):
    """Minimal provider adapter contract for source discovery and parsing."""

    provider_id: str

    def iter_session_files(self, source_dir: Path) -> Iterator[Path]:
        """Yield raw provider session files in deterministic order."""

    def load_source_index(self, home_dir: Path) -> dict[str, JsonObject]:
        """Load optional provider-native summary/index data keyed by session id."""

    def parse_session_file(self, path: Path, source_dir: Path) -> ParsedSession:
        """Parse one raw provider session file into the normalized session model."""

    def capabilities(self) -> ProviderCapabilities:
        """Return small capability flags for the provider."""
