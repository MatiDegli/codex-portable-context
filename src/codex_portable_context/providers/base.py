"""Small provider adapter interface for raw session sources."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any, Protocol

from codex_portable_context.core.parsing import JsonObject, ParsedSession


class SessionProviderAdapter(Protocol):
    """Minimal provider adapter contract for source discovery and parsing."""

    provider_id: str

    def iter_session_files(self, source_dir: Path) -> Iterator[Path]:
        """Yield raw provider session files in deterministic order."""

    def load_source_index(self, home_dir: Path) -> dict[str, JsonObject]:
        """Load optional provider-native summary/index data keyed by session id."""

    def parse_session_file(self, path: Path, source_dir: Path) -> ParsedSession:
        """Parse one raw provider session file into the normalized session model."""

    def capabilities(self) -> dict[str, Any]:
        """Return small capability flags for the provider."""
