"""Incremental export state helpers for the Python v2 mirror exporter."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from .contract import EXPORT_FORMAT_VERSION
from .redaction import RedactionContext


@dataclass(frozen=True, slots=True)
class StateRecord:
    """One persisted state record keyed by source-relative path."""

    source_relpath: str
    input_signature: str
    session_id: str
    metadata_relpath: str
    markdown_relpath: str


def file_fingerprint(path: Path) -> str:
    """Return the file fingerprint used by incremental export."""

    stat = path.stat()
    return f"{stat.st_mtime_ns}:{stat.st_size}"


def build_input_signature(
    *,
    source_file: Path,
    session_id: str,
    thread_name: str | None,
    updated_at: str | None,
    redact: bool,
    profile_name: str,
    include_context: bool,
    include_tools: bool,
    include_events: bool,
    redaction_context: RedactionContext,
) -> str:
    """Build the deterministic incremental signature for one export input."""

    payload = {
        "export_format_version": EXPORT_FORMAT_VERSION,
        "source_fingerprint": file_fingerprint(source_file),
        "session_id": session_id,
        "thread_name": thread_name or "",
        "updated_at": updated_at or "",
        "redact_mode": redact,
        "profile_name": profile_name,
        "markdown_includes": {
            "context": include_context,
            "tools": include_tools,
            "events": include_events,
        },
        "redaction_context": {
            "user_name": redaction_context.user_name,
            "home_dir": redaction_context.home_dir,
            "hostname_short": redaction_context.hostname_short,
            "hostname_fqdn": redaction_context.hostname_fqdn,
        },
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8"))
    return digest.hexdigest()


def load_state(path: Path) -> dict[str, StateRecord]:
    """Load the local mirror state file keyed by source_relpath."""

    if not path.is_file() or path.stat().st_size == 0:
        return {}

    state: dict[str, StateRecord] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            raw = json.loads(stripped)
            record = StateRecord(
                source_relpath=str(raw["source_relpath"]),
                input_signature=str(raw["input_signature"]),
                session_id=str(raw["session_id"]),
                metadata_relpath=str(raw["metadata_relpath"]),
                markdown_relpath=str(raw["markdown_relpath"]),
            )
            state[record.source_relpath] = record
    return state


def save_state(path: Path, records: list[StateRecord]) -> None:
    """Write the local mirror state file."""

    lines = [
        json.dumps(
            {
                "source_relpath": record.source_relpath,
                "input_signature": record.input_signature,
                "session_id": record.session_id,
                "metadata_relpath": record.metadata_relpath,
                "markdown_relpath": record.markdown_relpath,
            },
            separators=(",", ":"),
            ensure_ascii=False,
        )
        for record in records
    ]
    text = "\n".join(lines)
    if text:
        text += "\n"
    path.write_text(text, encoding="utf-8")
