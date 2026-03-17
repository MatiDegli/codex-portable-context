"""Small provider adapter interface for raw session sources."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from codex_portable_context.core.parsing import ParsedSession

JsonObject = dict[str, Any]


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    """Small capability set that lets the core adapt provider differences safely."""

    supports_tools: bool
    supports_reader_html: bool
    supports_handoff_source_enrichment: bool
    supports_context_sections: bool
    supports_redaction_source_context: bool
    supports_latest_selection: bool


@dataclass(frozen=True, slots=True)
class ProviderSourceContext:
    """Provider-native source context prepared once per export run."""

    native_index_by_session_id: dict[str, JsonObject] | None = None


@dataclass(frozen=True, slots=True)
class ProviderSessionDescriptor:
    """Normalized provider session identity and recency details for one export unit."""

    provider: str
    provider_session_id: str
    session_id: str
    source_file: Path
    source_relpath: str
    thread_name: str | None = None
    updated_at: str | None = None


class SessionProviderAdapter(Protocol):
    """Minimal provider adapter contract for source discovery and parsing."""

    provider_id: str

    def default_home_dir(self) -> Path:
        """Return the default provider home directory."""

    def default_source_dir(self, home_dir: Path) -> Path:
        """Return the default source directory for one provider home."""

    def iter_session_files(self, source_dir: Path) -> Iterator[Path]:
        """Yield raw provider session files in deterministic order."""

    def build_source_context(self, home_dir: Path) -> ProviderSourceContext:
        """Build provider-native source context for one export run."""

    def describe_session(
        self,
        *,
        parsed: ParsedSession,
        source_context: ProviderSourceContext,
        session_file: Path,
    ) -> ProviderSessionDescriptor:
        """Return normalized provider session identity and recency details."""

    def parse_session_file(self, path: Path, source_dir: Path) -> ParsedSession:
        """Parse one raw provider session file into the normalized session model."""

    def capabilities(self) -> ProviderCapabilities:
        """Return small capability flags for the provider."""
