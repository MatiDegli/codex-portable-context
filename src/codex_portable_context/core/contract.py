"""Stable mirror layout and field expectations for the v2 Python core."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

LANDING_FILENAME = "README.md"
LANDING_MARKER = "<!-- codex-portable-context: derived-mirror -->"
HTML_INDEX_FILENAME = "index.html"
INDEX_FILENAME = "sessions-index.jsonl"
STATE_FILENAME = ".codex-session-mirror-state.jsonl"
HANDOFFS_DIRNAME = "handoffs"
METADATA_DIRNAME = "metadata"
SESSIONS_DIRNAME = "sessions"
READER_DIRNAME = "reader"
EXPORT_FORMAT_VERSION = 7

MARKDOWN_FILTER_RULES = (
    "Routine token_count events are omitted from Markdown.",
    "turn_context records are omitted from Markdown.",
    (
        "Assistant response_item message wrappers are omitted when "
        "agent_message events already carry the readable text."
    ),
    "Notable lifecycle events are grouped in a separate Markdown section.",
    "Raw source session files remain the authoritative input.",
)

SUMMARY_REQUIRED_FIELDS = (
    "preview",
    "activity",
    "environment",
    "detail_line",
    "one_line",
)

SUMMARY_OPTIONAL_FIELDS = (
    "first_user_message",
    "last_user_message",
    "last_assistant_message",
)

REDACTION_REPORT_REQUIRED_FIELDS = (
    "enabled",
    "best_effort",
    "note",
    "artifacts",
    "placeholder_totals",
    "total_replacements",
)

INDEX_REQUIRED_FIELDS = (
    "session_id",
    "title",
    "export_profile",
    "exported_at",
    "source_relpath",
    "metadata_relpath",
    "markdown_relpath",
    "redacted",
    "markdown_includes",
    "summary",
    "redaction_report",
)

INDEX_OPTIONAL_FIELDS = (
    "thread_name",
    "updated_at",
    "session_timestamp",
    "cwd",
    "originator",
    "source",
    "model_provider",
    "cli_version",
    "reader_relpath",
)

METADATA_OPTIONAL_FIELDS = INDEX_OPTIONAL_FIELDS + ("source_file", "markdown_filter_rules")

STATE_REQUIRED_FIELDS = (
    "source_relpath",
    "input_signature",
    "session_id",
    "metadata_relpath",
    "markdown_relpath",
    "reader_relpath",
)


@dataclass(frozen=True, slots=True)
class MirrorLayout:
    """Resolved paths for a derived mirror output directory."""

    out_dir: Path

    @property
    def landing_path(self) -> Path:
        return self.out_dir / LANDING_FILENAME

    @property
    def index_path(self) -> Path:
        return self.out_dir / INDEX_FILENAME

    @property
    def reader_index_path(self) -> Path:
        return self.out_dir / HTML_INDEX_FILENAME

    @property
    def state_path(self) -> Path:
        return self.out_dir / STATE_FILENAME

    @property
    def metadata_dir(self) -> Path:
        return self.out_dir / METADATA_DIRNAME

    @property
    def handoffs_dir(self) -> Path:
        return self.out_dir / HANDOFFS_DIRNAME

    @property
    def sessions_dir(self) -> Path:
        return self.out_dir / SESSIONS_DIRNAME

    @property
    def reader_dir(self) -> Path:
        return self.out_dir / READER_DIRNAME

    def metadata_relpath(self, session_id: str) -> str:
        return f"{METADATA_DIRNAME}/{session_id}.json"

    def markdown_relpath(self, session_id: str) -> str:
        return f"{SESSIONS_DIRNAME}/{session_id}.md"

    def reader_relpath(self, session_id: str) -> str:
        return f"{READER_DIRNAME}/{session_id}.html"

    def handoff_markdown_relpath(self, session_id: str) -> str:
        return f"{HANDOFFS_DIRNAME}/{session_id}.md"

    def handoff_json_relpath(self, session_id: str) -> str:
        return f"{HANDOFFS_DIRNAME}/{session_id}.json"

    def metadata_path(self, session_id: str) -> Path:
        return self.out_dir / self.metadata_relpath(session_id)

    def markdown_path(self, session_id: str) -> Path:
        return self.out_dir / self.markdown_relpath(session_id)

    def reader_path(self, session_id: str) -> Path:
        return self.out_dir / self.reader_relpath(session_id)

    def handoff_markdown_path(self, session_id: str) -> Path:
        return self.out_dir / self.handoff_markdown_relpath(session_id)

    def handoff_json_path(self, session_id: str) -> Path:
        return self.out_dir / self.handoff_json_relpath(session_id)
