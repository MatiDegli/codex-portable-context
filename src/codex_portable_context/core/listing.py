"""Derived mirror list helpers for the Python v2 CLI."""

from __future__ import annotations

import json
from dataclasses import dataclass

from .index import MirrorEntry, entry_relpath, entry_session_id, entry_title, sort_entries
from .markdown import pretty_timestamp


@dataclass(frozen=True, slots=True)
class ListOptions:
    """Read-oriented list rendering options."""

    limit: int = 0
    title_filter: str = ""
    id_filter: str = ""
    show_summary: bool = False
    show_details: bool = False
    show_redaction: bool = False


def filter_entries(entries: list[MirrorEntry], options: ListOptions) -> list[MirrorEntry]:
    """Filter and sort mirror entries for list-style views."""

    title_filter = options.title_filter.lower()
    id_filter = options.id_filter.lower()
    filtered: list[MirrorEntry] = []

    for entry in sort_entries(entries):
        title = entry_title(entry).lower()
        session_id = entry_session_id(entry).lower()
        if title_filter and title_filter not in title:
            continue
        if id_filter and id_filter not in session_id:
            continue
        filtered.append(entry)

    if options.limit > 0:
        return filtered[: options.limit]
    return filtered


def entries_to_json(entries: list[MirrorEntry]) -> str:
    """Serialize filtered entries as pretty JSON."""

    return json.dumps(entries, indent=2, ensure_ascii=False) + "\n"


def render_entry_table(entries: list[MirrorEntry], options: ListOptions) -> str:
    """Render a readable terminal table for filtered mirror entries."""

    lines = [
        f"{'SESSION ID':<36}  {'UPDATED':<19}  {'TITLE':<44}  MARKDOWN",
    ]

    for entry in entries:
        lines.append(
            f"{entry_session_id(entry):<36}  "
            f"{pretty_timestamp(_sort_timestamp(entry)):<19}  "
            f"{truncate(entry_title(entry), 44):<44}  "
            f"{entry_relpath(entry, 'markdown')}"
        )
        if options.show_summary:
            preview = _summary_value(entry, "preview") or _summary_value(entry, "one_line")
            if preview:
                lines.append(render_labeled_line("preview", preview))
        if options.show_details:
            activity = _summary_value(entry, "activity")
            detail_line = _summary_value(entry, "detail_line")
            environment = _summary_value(entry, "environment")
            if activity:
                lines.append(render_labeled_line("activity", activity))
            elif detail_line:
                lines.append(render_labeled_line("details", detail_line))
            if environment:
                lines.append(render_labeled_line("environment", environment))
        if options.show_redaction:
            lines.append(render_labeled_line("redaction", redaction_line(entry)))

    return "\n".join(lines) + "\n"


def truncate(text: str, limit: int) -> str:
    """Truncate a label for fixed-width table output."""

    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def render_labeled_line(label: str, value: str) -> str:
    """Render a compact labeled detail line."""

    return f"  {label:<11} {value}"


def redaction_line(entry: MirrorEntry) -> str:
    """Return a compact redaction summary for one entry."""

    report = entry.get("redaction_report")
    report_dict = report if isinstance(report, dict) else {}
    if not report_dict.get("enabled", False):
        return "off"

    placeholder_totals = report_dict.get("placeholder_totals")
    placeholder_dict = placeholder_totals if isinstance(placeholder_totals, dict) else {}
    return (
        "on, replacements: "
        f"{int(report_dict.get('total_replacements', 0))}, "
        f"home: {int(placeholder_dict.get('home', 0))}, "
        f"user: {int(placeholder_dict.get('user', 0))}, "
        f"host: {int(placeholder_dict.get('host', 0))}, "
        f"secret: {int(placeholder_dict.get('secret', 0))}"
    )


def _summary_value(entry: MirrorEntry, key: str) -> str:
    summary = entry.get("summary")
    summary_dict = summary if isinstance(summary, dict) else {}
    value = summary_dict.get(key)
    return str(value) if value else ""


def _sort_timestamp(entry: MirrorEntry) -> str:
    for key in ("updated_at", "session_timestamp", "exported_at"):
        value = entry.get(key)
        if value:
            return str(value)
    return ""
