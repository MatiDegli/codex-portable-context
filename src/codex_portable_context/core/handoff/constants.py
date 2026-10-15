"""Module-level constants and small dataclasses shared by the handoff modules."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

RECENT_ACTION_LOOKBACK = 80


LINKED_CHILD_SESSION_LIMIT = 12


PROVIDER_CAPABILITY_KEYS = (
    "supports_tools",
    "supports_reader_html",
    "supports_handoff_source_enrichment",
    "supports_context_sections",
    "supports_redaction_source_context",
    "supports_latest_selection",
)


SOURCE_MODE_VALUES = (
    "local_source_session",
    "derived_mirror_only",
)


SOURCE_SECTION_KEYS = (
    "session",
    "continuation_brief",
    "resolved_state",
    "current_state",
    "continuity_freshness",
    "roadmap_evidence",
    "repo_evidence",
    "changed_artifacts",
    "decisions_and_invariants",
    "reentry_posture",
    "restart_prompt",
    "recent_window",
    "recent_notable_events",
    "recent_tool_activity",
    "compaction_summaries",
    "linked_child_sessions",
)


SECTION_SOURCE_VALUES = (
    "source_backed",
    "derived_mirror",
    "provider_enrichment",
    "unavailable",
    "not_supported",
)


ROADMAP_KNOWN_RELATIVE_PATHS = (
    "docs/next_steps.md",
    "docs/roadmap.md",
    "docs/continuity-bridge-roadmap.md",
    "ROADMAP.md",
    "roadmap.md",
)


ROADMAP_GLOB_PATTERNS = (
    "docs/*roadmap*.md",
    "docs/*next*step*.md",
    "docs/*strategy*.md",
    "docs/*decision*.md",
    "docs/*status*.md",
)


ROADMAP_SIGNAL_MARKERS = (
    "active track",
    "acceptance checks",
    "current priority",
    "current state",
    "decision",
    "invariant",
    "next best action",
    "next step",
    "next steps",
    "non-goal",
    "paused",
    "phase ",
    "priority",
    "roadmap",
    "source of truth",
    "rejected",
    "risk",
    "status",
    "validation",
    "frente principal",
    "linea principal",
    "línea principal",
    "pausado",
    "prioridad",
    "siguiente paso",
)


REPO_EVIDENCE_STORE_THRESHOLD = 0.50


REPO_EVIDENCE_PROMPT_THRESHOLD = 0.75


REPO_EVIDENCE_SYNTHESIS_THRESHOLD = 0.90


REPO_EVIDENCE_KNOWN_RELATIVE_PATHS = (
    "README.md",
    "conventions.md",
    "AGENTS.md",
    "CLAUDE.md",
    "docs/next_steps.md",
)


REPO_EVIDENCE_GLOB_PATTERNS = (
    "docs/*roadmap*.md",
    "docs/*status*.md",
    ".github/workflows/*.yml",
    ".github/workflows/*.yaml",
    "pyproject.toml",
    "package.json",
)


REPO_EVIDENCE_EXCLUDED_PARTS = {
    ".agent-bridge",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    ".vscode",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "out",
}


@dataclass(frozen=True, slots=True)
class HandoffResult:
    """Written handoff artifact paths."""

    session_id: str
    markdown_path: Path
    json_path: Path


@dataclass(frozen=True, slots=True)
class HandoffUserTurn:
    """One user-message boundary that can be used for historical snapshots."""

    index: int
    timestamp: str
    preview: str
