"""Small text, timestamp and payload helpers."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..parsing import RenderBlock
from ..redaction import RedactionContext, redact_text


def _render_block_payload(
    block: RenderBlock,
    *,
    redacted: bool,
    context: RedactionContext,
) -> dict[str, Any]:
    text = block.text
    if redacted:
        text = redact_text(text, context).text
    return {
        "kind": block.kind,
        "label": block.label,
        "timestamp": block.timestamp,
        "role": block.role,
        "tool_name": block.tool_name,
        "call_id": block.call_id,
        "text": _excerpt_text(text, limit=600),
    }


def _excerpt_text(text: str, *, limit: int) -> str:
    stripped = text.strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[: max(0, limit - 3)].rstrip() + "..."


def _iso_now() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _timestamp_after(candidate: str | None, reference: str) -> bool:
    if not candidate:
        return False
    return candidate > reference


def _parse_tool_call_json(text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string(value: Any) -> str:
    return str(value) if value is not None else ""


def _handoff_relpath(path: str) -> str:
    if not path:
        return ""
    return "../" + path.lstrip("./")


def _handoff_sibling_relpath(path: str) -> str:
    if not path:
        return ""
    return "./" + Path(path).name
