"""Extractive handoff bundle helpers for derived mirrors."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from codex_portable_context.providers import get_provider_adapter

from .discovery import mirror_layout
from .index import MirrorEntry, entry_path
from .markdown import pretty_timestamp
from .parsing import ParsedSession, RenderBlock
from .redaction import RedactionContext, redact_text


@dataclass(frozen=True, slots=True)
class HandoffResult:
    """Written handoff artifact paths."""

    session_id: str
    markdown_path: Path
    json_path: Path


def generate_handoff(entry: MirrorEntry, out_dir: Path | None = None) -> HandoffResult:
    """Write an extractive handoff bundle for one derived mirror entry."""

    layout = mirror_layout(out_dir)
    layout.handoffs_dir.mkdir(parents=True, exist_ok=True)

    session_id = str(entry["session_id"])
    metadata_path = entry_path(entry, "metadata", layout.out_dir)
    markdown_path = entry_path(entry, "markdown", layout.out_dir)
    reader_relpath = str(
        entry.get("reader_relpath") or layout.reader_relpath(session_id)
    )

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    transcript_text = markdown_path.read_text(encoding="utf-8")
    cwd = _string(metadata.get("cwd"))

    parsed = _load_source_session(metadata)
    handoff = _build_handoff_payload(
        metadata=metadata,
        transcript_text=transcript_text,
        parsed=parsed,
        reader_relpath=reader_relpath,
        out_dir=layout.out_dir,
        cwd=Path(cwd).expanduser() if cwd else None,
    )

    handoff_json_path = layout.handoff_json_path(session_id)
    handoff_markdown_path = layout.handoff_markdown_path(session_id)
    handoff_json_path.write_text(
        json.dumps(handoff, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    handoff_markdown_path.write_text(
        render_handoff_markdown(handoff),
        encoding="utf-8",
    )

    return HandoffResult(
        session_id=session_id,
        markdown_path=handoff_markdown_path,
        json_path=handoff_json_path,
    )


def render_handoff_markdown(handoff: dict[str, Any]) -> str:
    """Render a readable handoff Markdown document."""

    session = _as_dict(handoff.get("session"))
    artifacts = _as_dict(handoff.get("artifacts"))
    continuity_entry = _as_dict(handoff.get("continuity_entry"))
    current_state = _as_dict(handoff.get("current_state"))
    open_loops = _as_dict(handoff.get("open_loops"))
    source = _as_dict(handoff.get("source_availability"))
    template = _as_dict(handoff.get("operator_note_template"))
    recent_actions = _as_list(handoff.get("recent_actions"))
    recent_window = _as_list(handoff.get("recent_window"))
    recent_events = _as_list(handoff.get("recent_notable_events"))
    recent_tools = _as_list(handoff.get("recent_tool_activity"))
    transcript_link = _handoff_relpath(_string(artifacts.get("markdown_relpath")))
    metadata_link = _handoff_relpath(_string(artifacts.get("metadata_relpath")))
    reader_link = _handoff_relpath(_string(artifacts.get("reader_relpath")))
    handoff_json_link = _handoff_sibling_relpath(_string(artifacts.get("handoff_json_relpath")))
    primary_label = _string(
        continuity_entry.get("primary_artifact_relpath")
    ) or _string(artifacts.get("handoff_markdown_relpath"))
    transcript_fallback_label = _string(
        continuity_entry.get("transcript_fallback_relpath")
    ) or _string(artifacts.get("markdown_relpath"))
    reader_fallback_label = _string(
        continuity_entry.get("reader_fallback_relpath")
    ) or _string(artifacts.get("reader_relpath"))
    primary_link = _handoff_sibling_relpath(
        _string(continuity_entry.get("primary_artifact_relpath"))
    )
    transcript_fallback_link = _handoff_relpath(
        _string(continuity_entry.get("transcript_fallback_relpath"))
    )
    reader_fallback_link = _handoff_relpath(
        _string(continuity_entry.get("reader_fallback_relpath"))
    )
    updated_at = pretty_timestamp(
        _string(handoff.get("updated_at")) or _string(handoff.get("session_timestamp"))
    )
    generated_at = pretty_timestamp(_string(handoff.get("generated_at")))
    repo_state = (
        "clean"
        if artifacts.get("repo_clean") is True
        else "dirty"
        if artifacts.get("repo_clean") is False
        else "unknown"
    )

    lines: list[str] = [
        f"# Handoff: {session.get('title') or handoff.get('session_id')}",
        "",
        (
            "This handoff bundle is extractive and local-first. "
            "It does not resume or write back into Codex state."
        ),
        "",
        "## Snapshot",
        "",
        f"- Session ID: `{handoff.get('session_id')}`",
        f"- Updated: `{updated_at}`",
        f"- Exported At: `{generated_at}`",
        f"- Redacted: `{'yes' if handoff.get('redacted') else 'no'}`",
        f"- Source session available locally: `{'yes' if source.get('available') else 'no'}`",
        "",
        f"- Started with: {session.get('preview') or 'n/a'}",
        f"- Last substantive user request: {session.get('last_substantive_user_request') or 'n/a'}",
        f"- Latest assistant reply: {session.get('last_assistant_message') or 'n/a'}",
        f"- Activity: {session.get('activity') or 'n/a'}",
        f"- Environment: {session.get('environment') or 'n/a'}",
        "",
        "## Current State",
        "",
        f"- Status: `{current_state.get('status') or 'unknown'}`",
        f"- Current focus: {current_state.get('current_focus') or 'n/a'}",
        f"- Last meaningful outcome: {current_state.get('last_meaningful_outcome') or 'n/a'}",
        f"- Next recommended action: {current_state.get('next_recommended_action') or 'n/a'}",
        f"- Known blocker: {current_state.get('known_blocker') or 'none'}",
        "",
        "## Continuity Entry",
        "",
        f"- Start here: [{primary_label}]({primary_link})",
        f"- Machine-readable state: [{artifacts.get('handoff_json_relpath')}]({handoff_json_link})",
        f"- Transcript fallback: [{transcript_fallback_label}]({transcript_fallback_link})",
        f"- Reader fallback: [{reader_fallback_label}]({reader_fallback_link})",
        "",
        "## Artifacts",
        "",
        f"- Transcript: [{artifacts.get('markdown_relpath')}]({transcript_link})",
        f"- Metadata: [{artifacts.get('metadata_relpath')}]({metadata_link})",
        f"- Reader: [{artifacts.get('reader_relpath')}]({reader_link})",
        f"- Handoff Markdown: `{artifacts.get('handoff_markdown_relpath') or 'n/a'}`",
        f"- Handoff JSON: [{artifacts.get('handoff_json_relpath')}]({handoff_json_link})",
        f"- Repo root: `{artifacts.get('repo_root') or 'n/a'}`",
        f"- Branch: `{artifacts.get('repo_branch') or 'n/a'}`",
        f"- HEAD commit: `{artifacts.get('repo_head_commit') or 'n/a'}`",
        f"- Repo state: `{repo_state}`",
        "",
        "## Operator Note Template",
        "",
        f"- What matters now: {template.get('what_matters_now')}",
        f"- Next step: {template.get('next_step')}",
        f"- Known risks: {template.get('known_risks')}",
        "",
    ]

    if recent_actions:
        lines.extend(["## Recent Actions (normalized)", ""])
        for action in recent_actions:
            lines.append(f"- {action}")
        lines.append("")

    workflow = _as_list(continuity_entry.get("destination_workflow"))
    if workflow:
        lines.extend(["### Destination Workflow", ""])
        for step in workflow:
            lines.append(f"- {step}")
        lines.append("")

    lines.extend(
        [
            "## Open Loops / Risks",
            "",
            f"- Pending validation: {open_loops.get('pending_validation') or 'none'}",
            f"- Open question: {open_loops.get('open_question') or 'none'}",
            f"- Unresolved failure: {open_loops.get('unresolved_failure') or 'none'}",
            f"- Expected next command: `{open_loops.get('expected_next_command') or 'none'}`",
            f"- Operational risk: {open_loops.get('operational_risk') or 'none'}",
            "",
        ]
    )

    excerpt = _string(handoff.get("transcript_excerpt"))
    if excerpt:
        lines.extend(
            [
                "## Transcript Excerpt",
                "",
                excerpt,
                "",
            ]
        )

    if recent_window:
        lines.extend(["## Recent Conversation Window (audit trail)", ""])
        for item in recent_window:
            block = _as_dict(item)
            lines.extend(
                [
                    f"### {block.get('label')}",
                    "",
                    f"- Kind: `{block.get('kind')}`",
                    f"- Timestamp: `{pretty_timestamp(_string(block.get('timestamp')) )}`",
                    block.get("text") or "_No text available._",
                    "",
                ]
            )

    if recent_events:
        lines.extend(["## Recent Notable Events (audit trail)", ""])
        for item in recent_events:
            event = _as_dict(item)
            timestamp = pretty_timestamp(_string(event.get("timestamp")))
            line = f"- `{timestamp}` {event.get('label')}: {event.get('text')}"
            lines.extend(
                [
                    line,
                ]
            )
        lines.append("")

    if recent_tools:
        lines.extend(["## Recent Tool Activity (audit trail)", ""])
        for item in recent_tools:
            tool = _as_dict(item)
            lines.extend(
                [
                    f"### {tool.get('label')}",
                    "",
                    f"- Timestamp: `{pretty_timestamp(_string(tool.get('timestamp')) )}`",
                    f"- Tool: `{tool.get('tool_name') or 'unknown'}`",
                    tool.get("text") or "_No text available._",
                    "",
                ]
            )

    return "\n".join(lines)


def _build_handoff_payload(
    *,
    metadata: dict[str, Any],
    transcript_text: str,
    parsed: ParsedSession | None,
    reader_relpath: str,
    out_dir: Path,
    cwd: Path | None,
) -> dict[str, Any]:
    summary = _as_dict(metadata.get("summary"))
    redacted = bool(metadata.get("redacted"))
    redaction_context = RedactionContext.detect()
    last_substantive_user_request = (
        _last_substantive_user_request(parsed.user_messages)
        if parsed
        else _string(summary.get("last_user_message"))
    )
    recent_actions = (
        _recent_actions(parsed.conversation_entries, redacted=redacted, context=redaction_context)
        if parsed
        else []
    )
    current_state = _build_current_state(
        parsed=parsed,
        summary=summary,
        last_substantive_user_request=last_substantive_user_request,
        recent_actions=recent_actions,
    )
    repo_state = _detect_repo_state(cwd)
    open_loops = _build_open_loops(
        parsed=parsed,
        current_state=current_state,
        last_substantive_user_request=last_substantive_user_request,
        recent_actions=recent_actions,
        source_available=parsed is not None,
        repo_state=repo_state,
        redacted=redacted,
        context=redaction_context,
    )
    layout = mirror_layout(out_dir)
    session_id = _string(metadata.get("session_id"))
    handoff_markdown_relpath = str(layout.handoff_markdown_relpath(session_id))
    handoff_json_relpath = str(layout.handoff_json_relpath(session_id))
    continuity_entry = _build_continuity_entry(
        metadata=metadata,
        handoff_markdown_relpath=handoff_markdown_relpath,
        handoff_json_relpath=handoff_json_relpath,
        reader_relpath=reader_relpath,
    )

    recent_window = (
        [
            _render_block_payload(block, redacted=redacted, context=redaction_context)
            for block in parsed.conversation_entries[-8:]
        ]
        if parsed
        else []
    )
    recent_events = (
        [
            _render_block_payload(block, redacted=redacted, context=redaction_context)
            for block in parsed.notable_events[-5:]
        ]
        if parsed
        else []
    )
    recent_tools = (
        [
            _render_block_payload(block, redacted=redacted, context=redaction_context)
            for block in parsed.conversation_entries
            if block.kind == "tool_call"
        ][-5:]
        if parsed
        else []
    )

    return {
        "handoff_schema_version": 1,
        "provider": metadata.get("provider") or "codex",
        "provider_session_id": metadata.get("provider_session_id"),
        "generated_at": _iso_now(),
        "session_id": metadata.get("session_id"),
        "title": metadata.get("title"),
        "updated_at": metadata.get("updated_at"),
        "session_timestamp": metadata.get("session_timestamp"),
        "redacted": redacted,
        "session": {
            "title": metadata.get("title"),
            "preview": summary.get("preview", ""),
            "first_user_message": summary.get("first_user_message", ""),
            "last_user_message": summary.get("last_user_message", ""),
            "last_substantive_user_request": last_substantive_user_request,
            "last_assistant_message": summary.get("last_assistant_message", ""),
            "activity": summary.get("activity", ""),
            "environment": summary.get("environment", ""),
            "detail_line": summary.get("detail_line", ""),
            "one_line": summary.get("one_line", ""),
        },
        "current_state": current_state,
        "continuity_entry": continuity_entry,
        "open_loops": open_loops,
        "artifacts": {
            "metadata_relpath": str(metadata.get("metadata_relpath") or ""),
            "markdown_relpath": str(metadata.get("markdown_relpath") or ""),
            "reader_relpath": reader_relpath,
            "handoff_markdown_relpath": handoff_markdown_relpath,
            "handoff_json_relpath": handoff_json_relpath,
            "repo_root": repo_state["repo_root"],
            "repo_branch": repo_state["repo_branch"],
            "repo_head_commit": repo_state["repo_head_commit"],
            "repo_clean": repo_state["repo_clean"],
        },
        "source_availability": {
            "available": parsed is not None,
            "exact_recent_window": parsed is not None,
            "source_file": metadata.get("source_file"),
            "note": (
                "Recent window and tool activity were extracted from the local source session."
                if parsed is not None
                else "Only derived mirror data was available locally."
            ),
        },
        "recent_actions": recent_actions,
        "recent_window": recent_window,
        "recent_notable_events": recent_events,
        "recent_tool_activity": recent_tools,
        "operator_note_template": {
            "what_matters_now": "",
            "next_step": "",
            "known_risks": "",
        },
        "transcript_excerpt": _excerpt_text(transcript_text, limit=900),
    }


def _load_source_session(metadata: dict[str, Any]) -> ParsedSession | None:
    provider_id = _string(metadata.get("provider")) or "codex"
    source_file_value = metadata.get("source_file")
    source_relpath_value = metadata.get("source_relpath")
    if not isinstance(source_file_value, str) or not source_file_value.strip():
        return None
    if not isinstance(source_relpath_value, str) or not source_relpath_value.strip():
        return None

    source_file = Path(source_file_value).expanduser()
    if not source_file.is_file():
        return None

    source_dir = _infer_source_dir(source_file.resolve(), source_relpath_value)
    adapter = get_provider_adapter(provider_id)
    return adapter.parse_session_file(source_file.resolve(), source_dir)


def _infer_source_dir(source_file: Path, source_relpath: str) -> Path:
    current = source_file
    for _ in PurePosixPath(source_relpath).parts:
        current = current.parent
    return current


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


def _build_current_state(
    *,
    parsed: ParsedSession | None,
    summary: dict[str, Any],
    last_substantive_user_request: str,
    recent_actions: list[str],
) -> dict[str, str]:
    status = "in_progress"
    if parsed and parsed.notable_events:
        latest_event = parsed.notable_events[-1]
        lowered = latest_event.label.lower()
        if "turn_aborted" in lowered:
            status = "blocked"
        elif "task_complete" in lowered or "item_completed" in lowered:
            status = "done"

    current_focus = _current_focus_text(
        last_substantive_user_request or _string(summary.get("preview"))
    )
    last_meaningful_outcome = recent_actions[0] if recent_actions else _string(
        summary.get("last_assistant_message")
    )
    if status == "blocked":
        next_action = "Inspect the latest aborted turn or failing command before continuing."
        blocker = "Latest turn or task ended in an aborted state."
    elif status == "done":
        next_action = (
            "Review the handoff artifacts and decide whether to start a "
            "new follow-up task."
        )
        blocker = "none"
    else:
        next_action = (
            "Start a fresh local session and continue from this handoff's Current "
            "State and Open Loops."
        )
        blocker = "none"

    return {
        "status": status,
        "current_focus": current_focus,
        "last_meaningful_outcome": last_meaningful_outcome,
        "next_recommended_action": next_action,
        "known_blocker": blocker,
    }


def _build_continuity_entry(
    *,
    metadata: dict[str, Any],
    handoff_markdown_relpath: str,
    handoff_json_relpath: str,
    reader_relpath: str,
) -> dict[str, Any]:
    return {
        "primary_artifact_relpath": handoff_markdown_relpath,
        "machine_artifact_relpath": handoff_json_relpath,
        "transcript_fallback_relpath": str(metadata.get("markdown_relpath") or ""),
        "reader_fallback_relpath": reader_relpath,
        "destination_workflow": [
            "Read Current State, Recent Actions, and Open Loops first.",
            "Open the transcript only if more detail is needed.",
            "Start a fresh local provider session on the destination machine.",
            "Continue from derived context only; do not sync live provider state.",
        ],
    }


def _build_open_loops(
    *,
    parsed: ParsedSession | None,
    current_state: dict[str, str],
    last_substantive_user_request: str,
    recent_actions: list[str],
    source_available: bool,
    repo_state: dict[str, Any],
    redacted: bool,
    context: RedactionContext,
) -> dict[str, str]:
    unresolved_failure, expected_from_failure = _latest_failure_signal(
        parsed,
        redacted=redacted,
        context=context,
    )
    validation_ran = any(
        action == "ran ./scripts/validate-python-v2" for action in recent_actions
    )
    pending_validation = (
        "none"
        if validation_ran or current_state.get("status") == "done"
        else "Current changes have not been revalidated yet."
    )
    open_question = (
        last_substantive_user_request
        if last_substantive_user_request.rstrip().endswith("?")
        else "none"
    )
    if unresolved_failure != "none":
        expected_next_command = expected_from_failure or "none"
    elif pending_validation != "none":
        expected_next_command = "./scripts/validate-python-v2"
    else:
        expected_next_command = "none"

    if repo_state.get("repo_clean") is False:
        operational_risk = "Repo has uncommitted changes."
    elif not source_available:
        operational_risk = "Only derived mirror data is available locally."
    else:
        operational_risk = "none"

    return {
        "pending_validation": pending_validation,
        "open_question": open_question,
        "unresolved_failure": unresolved_failure,
        "expected_next_command": expected_next_command,
        "operational_risk": operational_risk,
    }


def _last_substantive_user_request(messages: list[str]) -> str:
    for message in reversed(messages):
        cleaned = _clean_user_request(message)
        if cleaned and not _is_trivial_request(cleaned):
            return cleaned
    return ""


def _clean_user_request(message: str) -> str:
    text = message.strip()
    marker = "## My request for Codex:"
    if marker in text:
        text = text.split(marker, 1)[1].strip()
    return _excerpt_text(" ".join(text.split()), limit=220)


def _current_focus_text(text: str) -> str:
    normalized = " ".join(text.strip().split())
    if not normalized:
        return ""

    first_sentence = re.split(r"(?<=[.!?])\s+", normalized, maxsplit=1)[0].strip()
    candidate = first_sentence or normalized
    return _excerpt_text(candidate, limit=140)


def _is_trivial_request(text: str) -> bool:
    lowered = text.strip().lower().rstrip(".!")
    return lowered in {
        "proceed",
        "procede",
        "continue",
        "continuar",
        "go on",
        "dale",
        "ok",
    }


def _recent_actions(
    conversation_entries: list[RenderBlock],
    *,
    redacted: bool,
    context: RedactionContext,
) -> list[str]:
    actions: list[str] = []
    seen: set[str] = set()

    for block in reversed(conversation_entries[-20:]):
        action = _normalized_action(block, redacted=redacted, context=context)
        if not action or action in seen:
            continue
        seen.add(action)
        actions.append(action)
        if len(actions) >= 6:
            break

    return actions


def _latest_failure_signal(
    parsed: ParsedSession | None,
    *,
    redacted: bool,
    context: RedactionContext,
) -> tuple[str, str]:
    if parsed is None:
        return ("none", "")

    calls_by_id = {
        block.call_id: block
        for block in parsed.conversation_entries
        if block.kind == "tool_call" and block.call_id
    }

    for block in reversed(parsed.conversation_entries[-20:]):
        if block.kind != "tool_output":
            continue
        failure_text = _tool_output_failure_text(block.text)
        if not failure_text:
            continue
        if redacted:
            failure_text = redact_text(failure_text, context).text
        command = ""
        source_call = calls_by_id.get(block.call_id or "")
        if source_call is not None:
            command = _expected_command_from_tool_call(source_call.text)
        return (_excerpt_text(failure_text, limit=180), command)

    for event in reversed(parsed.notable_events[-8:]):
        if "turn_aborted" in event.label.lower():
            return ("Latest turn ended in an aborted state.", "none")

    return ("none", "")


def _normalized_action(
    block: RenderBlock,
    *,
    redacted: bool,
    context: RedactionContext,
) -> str:
    if block.kind == "tool_output" and "Updated the following files:" in block.text:
        files = _updated_files_from_tool_output(block.text)
        if files:
            rendered_files = ", ".join(files[:3])
            return f"updated {rendered_files}"

    if block.kind != "tool_call":
        return ""

    tool_name = block.tool_name or ""
    if tool_name != "exec_command":
        return ""

    payload = _parse_tool_call_json(block.text)
    cmd = _string(payload.get("cmd"))
    if not cmd:
        return ""

    if "./scripts/validate-python-v2" in cmd:
        return "ran ./scripts/validate-python-v2"
    if "codex-session-mirror" in cmd and "codex-session-handoff" in cmd:
        return "regenerated derived mirror"
    if "codex-session-mirror" in cmd:
        return "regenerated derived mirror"
    if "codex-session-handoff" in cmd:
        return ""
    if "handoffs/" in cmd or "Handoff Markdown" in cmd or "Jump to handoff" in cmd:
        return "verified reader links to handoffs/"
    if re.search(r"\bpytest\b|\bmypy\b|\bruff\b", cmd):
        return f"ran `{_excerpt_text(cmd, limit=80)}`"
    if re.fullmatch(r"\s*pwd\s*", cmd):
        return "ran `pwd`"
    return ""


def _updated_files_from_tool_output(text: str) -> list[str]:
    payload = _parse_tool_call_json(text)
    output_text = _string(payload.get("output")) if payload else ""
    haystack = output_text or text

    files: list[str] = []
    capture = False
    for raw_line in haystack.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line in {
            "Updated the following files:",
            "Success. Updated the following files:",
        }:
            capture = True
            continue
        if not capture:
            continue
        if line.startswith("{") or line.startswith('"metadata"'):
            break
        normalized = re.sub(r"^[A-Z?]+\s+", "", line)
        if normalized and _looks_like_changed_path(normalized):
            files.append(Path(normalized).name or normalized)
    return files


def _looks_like_changed_path(text: str) -> bool:
    if text.startswith("/") or text.startswith("./"):
        return True
    path = Path(text)
    return len(path.parts) > 1 or "." in path.name


def _parse_tool_call_json(text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _expected_command_from_tool_call(text: str) -> str:
    payload = _parse_tool_call_json(text)
    cmd = _string(payload.get("cmd"))
    if not cmd:
        return "none"
    return _excerpt_text(cmd, limit=120)


def _tool_output_failure_text(text: str) -> str:
    payload = _parse_tool_call_json(text)
    output = _string(payload.get("output")) or text
    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        exit_code = metadata.get("exit_code")
        if isinstance(exit_code, int) and exit_code != 0:
            return output or f"Command exited with code {exit_code}."
    return ""


def _detect_repo_state(cwd: Path | None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "repo_root": "",
        "repo_branch": "",
        "repo_head_commit": "",
        "repo_clean": None,
    }
    if cwd is None or not cwd.exists():
        return result

    try:
        repo_root = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        branch = subprocess.run(
            ["git", "-C", repo_root, "rev-parse", "--abbrev-ref", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        head_commit = subprocess.run(
            ["git", "-C", repo_root, "rev-parse", "--short", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "-C", repo_root, "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return result

    result.update(
        {
            "repo_root": repo_root,
            "repo_branch": branch,
            "repo_head_commit": head_commit,
            "repo_clean": not bool(status),
        }
    )
    return result


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
