"""Extractive handoff bundle helpers for derived mirrors."""

from __future__ import annotations

import json
import re
import sqlite3
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from codex_portable_context.providers import get_provider_adapter

from .discovery import mirror_layout
from .html_reader import render_session_reader
from .index import MirrorEntry, entry_path
from .markdown import pretty_timestamp
from .parsing import ParsedSession, RenderBlock
from .redaction import RedactionContext, redact_text

RECENT_ACTION_LOOKBACK = 80
LINKED_CHILD_SESSION_LIMIT = 12


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

    metadata_text = metadata_path.read_text(encoding="utf-8")
    metadata = json.loads(metadata_text)
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
    reader_path = layout.reader_path(session_id)
    reader_path.parent.mkdir(parents=True, exist_ok=True)
    reader_path.write_text(
        render_session_reader(
            entry=metadata,
            metadata_text=metadata_text,
            markdown_text=transcript_text,
            handoff=handoff,
        ),
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
    continuation_brief = _as_dict(handoff.get("continuation_brief"))
    resolved_state = _as_dict(handoff.get("resolved_state"))
    restart_prompt = _as_dict(handoff.get("restart_prompt"))
    reentry_posture = _as_dict(handoff.get("reentry_posture"))
    continuity_entry = _as_dict(handoff.get("continuity_entry"))
    current_state = _as_dict(handoff.get("current_state"))
    open_loops = _as_dict(handoff.get("open_loops"))
    source = _as_dict(handoff.get("source_availability"))
    template = _as_dict(handoff.get("operator_note_template"))
    recent_actions = _as_list(handoff.get("recent_actions"))
    recent_window = _as_list(handoff.get("recent_window"))
    recent_events = _as_list(handoff.get("recent_notable_events"))
    recent_tools = _as_list(handoff.get("recent_tool_activity"))
    compaction_summaries = _as_list(handoff.get("compaction_summaries"))
    linked_child_sessions = _as_list(handoff.get("linked_child_sessions"))
    changed_artifacts = _as_dict(handoff.get("changed_artifacts"))
    decisions_and_invariants = _as_dict(handoff.get("decisions_and_invariants"))
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
    continuation_evidence = [
        f"- {item}"
        for item in _as_list(continuation_brief.get("evidence"))
    ] or ["- none"]
    resolution_status = resolved_state.get("request_resolution_status") or "unknown"
    remaining_local_paths = resolved_state.get("remaining_local_only_paths") or "n/a"
    contextual_request = resolved_state.get("contextual_user_request") or "n/a"
    inspection_order_lines = [
        f"- `{item}`"
        for item in _as_list(changed_artifacts.get("recommended_inspection_order"))
    ] or ["- none"]

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
        "## Continuation Brief",
        "",
        f"- What we were doing: {continuation_brief.get('what_we_were_doing') or 'n/a'}",
        f"- Why it mattered: {continuation_brief.get('why_it_mattered') or 'n/a'}",
        f"- Latest resolved request: {continuation_brief.get('latest_resolved_request') or 'n/a'}",
        f"- Last meaningful outcome: {continuation_brief.get('last_meaningful_outcome') or 'n/a'}",
        f"- Next best action: {continuation_brief.get('next_best_action') or 'n/a'}",
        f"- Do not do: {continuation_brief.get('do_not_do') or 'n/a'}",
        f"- Confidence: `{continuation_brief.get('confidence') or 'unknown'}`",
        "",
        "### Evidence",
        "",
        *continuation_evidence,
        "",
        "## Resolved State",
        "",
        f"- Latest user request: {resolved_state.get('latest_user_request') or 'n/a'}",
        f"- Contextual user request: {contextual_request}",
        f"- Request resolution status: `{resolution_status}`",
        f"- Resolution summary: {resolved_state.get('resolution_summary') or 'n/a'}",
        f"- Validation summary: {resolved_state.get('validation_summary') or 'n/a'}",
        f"- Commit summary: {resolved_state.get('commit_summary') or 'n/a'}",
        f"- Dirty state summary: {resolved_state.get('dirty_state_summary') or 'n/a'}",
        f"- Remaining local-only paths: {remaining_local_paths}",
        "",
        "## Changed / Key Artifacts",
        "",
        f"- Summary: {changed_artifacts.get('summary') or 'n/a'}",
        "",
        "### Recommended Inspection Order",
        "",
        *inspection_order_lines,
        "",
        "### Changed Paths",
        "",
        *_artifact_markdown_lines(_as_list(changed_artifacts.get("changed_paths"))),
        "",
        "### Key Paths",
        "",
        *_artifact_markdown_lines(_as_list(changed_artifacts.get("key_paths"))),
        "",
        "## Decisions / Invariants",
        "",
        f"- Confidence: `{decisions_and_invariants.get('confidence') or 'unknown'}`",
        "",
        "### Decisions",
        "",
        *_memory_markdown_lines(_as_list(decisions_and_invariants.get("decisions"))),
        "",
        "### Invariants",
        "",
        *_memory_markdown_lines(_as_list(decisions_and_invariants.get("invariants"))),
        "",
        "### Rejected Paths",
        "",
        *_memory_markdown_lines(_as_list(decisions_and_invariants.get("rejected_paths"))),
        "",
        "### Open Architecture Questions",
        "",
        *_memory_markdown_lines(
            _as_list(decisions_and_invariants.get("open_architecture_questions"))
        ),
        "",
        "## Re-Entry Posture",
        "",
        f"- Role hint: `{reentry_posture.get('role_hint') or 'unknown'}`",
        f"- Initial mode: `{reentry_posture.get('initial_mode') or 'unknown'}`",
        (
            "- Requires confirmation before changes: "
            f"`{'yes' if reentry_posture.get('requires_confirmation_before_changes') else 'no'}`"
        ),
        "",
        "### First Turn Contract",
        "",
        *[
            f"- {item}"
            for item in _as_list(reentry_posture.get("first_turn_contract"))
        ],
        "",
        "## Restart Prompt",
        "",
        (
            "Copy this into a fresh local session. It is a re-entry prompt, "
            "not a live session resume."
        ),
        "",
        "```text",
        _string(restart_prompt.get("text")) or "n/a",
        "```",
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

    if compaction_summaries:
        lines.extend(["## Compaction Summaries", ""])
        for item in compaction_summaries:
            summary = _as_dict(item)
            timestamp = pretty_timestamp(_string(summary.get("timestamp")))
            source_label = _string(summary.get("source")) or "context_compacted"
            lines.extend(
                [
                    f"### {timestamp}",
                    "",
                    f"- Source: `{source_label}`",
                ]
            )
            if summary.get("summary"):
                lines.append(f"- Summary: {summary.get('summary')}")
            if summary.get("prompt"):
                lines.append(f"- Prompt: {summary.get('prompt')}")
            lines.append("")

    if linked_child_sessions:
        lines.extend(["## Linked Child Sessions", ""])
        for item in linked_child_sessions:
            child = _as_dict(item)
            title = _string(child.get("title")) or _string(child.get("child_session_id"))
            session_id = _string(child.get("child_session_id"))
            markdown_relpath = _string(child.get("markdown_relpath"))
            handoff_relpath = _string(child.get("handoff_markdown_relpath"))
            lines.extend(
                [
                    f"### {title}",
                    "",
                    f"- Session ID: `{session_id}`",
                    f"- Status: `{child.get('status') or 'unknown'}`",
                    f"- Updated: `{pretty_timestamp(_string(child.get('updated_at')))}`",
                    f"- CWD: `{child.get('cwd') or 'n/a'}`",
                ]
            )
            agent_label = _child_agent_label(child)
            if agent_label:
                lines.append(f"- Agent: {agent_label}")
            if markdown_relpath:
                transcript_href = _handoff_relpath(markdown_relpath)
                lines.append(f"- Transcript: [{markdown_relpath}]({transcript_href})")
            if handoff_relpath:
                lines.append(
                    f"- Handoff: [{handoff_relpath}]({_handoff_sibling_relpath(handoff_relpath)})"
                )
            if child.get("first_user_message"):
                lines.append(f"- First user message: {child.get('first_user_message')}")
            if child.get("latest_assistant_message"):
                lines.append(f"- Latest assistant reply: {child.get('latest_assistant_message')}")
            lines.append("")

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
    latest_user_signal = _latest_substantive_user_signal(parsed=parsed, summary=summary)
    last_substantive_user_request = latest_user_signal["text"]
    recent_actions = (
        _recent_actions(parsed.conversation_entries, redacted=redacted, context=redaction_context)
        if parsed
        else []
    )
    repo_state = _detect_repo_state(cwd)
    resolved_state = _build_resolved_state(
        parsed=parsed,
        summary=summary,
        latest_user_signal=latest_user_signal,
        recent_actions=recent_actions,
        repo_state=repo_state,
        redacted=redacted,
        context=redaction_context,
    )
    current_state = _build_current_state(
        parsed=parsed,
        summary=summary,
        last_substantive_user_request=last_substantive_user_request,
        recent_actions=recent_actions,
        resolved_state=resolved_state,
    )
    open_loops = _build_open_loops(
        parsed=parsed,
        current_state=current_state,
        resolved_state=resolved_state,
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
    continuation_brief = _build_continuation_brief(
        session_title=_string(metadata.get("title")),
        current_state=current_state,
        resolved_state=resolved_state,
        open_loops=open_loops,
        source_available=parsed is not None,
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
    compaction_summaries = (
        _compaction_summaries(
            parsed.notable_events,
            redacted=redacted,
            context=redaction_context,
        )
        if parsed
        else []
    )
    linked_child_sessions = _linked_child_sessions(
        metadata=metadata,
        out_dir=out_dir,
        redacted=redacted,
        context=redaction_context,
    )
    changed_artifacts = _build_changed_artifacts(
        parsed=parsed,
        resolved_state=resolved_state,
        recent_window=recent_window,
        repo_state=repo_state,
        redacted=redacted,
        context=redaction_context,
    )
    decisions_and_invariants = _build_decisions_and_invariants(
        parsed=parsed,
        continuation_brief=continuation_brief,
        resolved_state=resolved_state,
        changed_artifacts=changed_artifacts,
        recent_window=recent_window,
        redacted=redacted,
        context=redaction_context,
    )
    continuation_brief["next_best_action"] = _next_best_action_for_brief(
        session_title=_string(metadata.get("title")),
        current_state=current_state,
        resolved_state=resolved_state,
        open_loops=open_loops,
        changed_artifacts=changed_artifacts,
        decisions_and_invariants=decisions_and_invariants,
    )
    artifacts = {
        "metadata_relpath": str(metadata.get("metadata_relpath") or ""),
        "markdown_relpath": str(metadata.get("markdown_relpath") or ""),
        "reader_relpath": reader_relpath,
        "handoff_markdown_relpath": handoff_markdown_relpath,
        "handoff_json_relpath": handoff_json_relpath,
        "repo_root": repo_state["repo_root"],
        "repo_branch": repo_state["repo_branch"],
        "repo_head_commit": repo_state["repo_head_commit"],
        "repo_clean": repo_state["repo_clean"],
        "repo_dirty_paths": repo_state["repo_dirty_paths"],
    }
    reentry_posture = _build_reentry_posture(
        continuation_brief=continuation_brief,
        resolved_state=resolved_state,
        decisions_and_invariants=decisions_and_invariants,
    )
    restart_prompt = _build_restart_prompt(
        session_id=session_id,
        session_title=_string(metadata.get("title")),
        artifacts=artifacts,
        continuation_brief=continuation_brief,
        resolved_state=resolved_state,
        open_loops=open_loops,
        reentry_posture=reentry_posture,
        changed_artifacts=changed_artifacts,
        decisions_and_invariants=decisions_and_invariants,
        linked_child_sessions=linked_child_sessions,
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
        "continuation_brief": continuation_brief,
        "resolved_state": resolved_state,
        "current_state": current_state,
        "changed_artifacts": changed_artifacts,
        "decisions_and_invariants": decisions_and_invariants,
        "reentry_posture": reentry_posture,
        "restart_prompt": restart_prompt,
        "continuity_entry": continuity_entry,
        "open_loops": open_loops,
        "artifacts": artifacts,
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
        "compaction_summaries": compaction_summaries,
        "linked_child_sessions": linked_child_sessions,
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


def _latest_substantive_user_signal(
    *,
    parsed: ParsedSession | None,
    summary: dict[str, Any],
) -> dict[str, str]:
    if parsed:
        signals: list[dict[str, str]] = []
        for block in reversed(parsed.conversation_entries):
            if block.kind != "user":
                continue
            cleaned = _clean_user_request(block.text)
            if cleaned and not _is_trivial_request(cleaned):
                signals.append({"text": cleaned, "timestamp": block.timestamp or ""})
                if len(signals) >= 2:
                    break
        if signals:
            latest = signals[0]
            previous = signals[1] if len(signals) > 1 else {"text": "", "timestamp": ""}
            context_dependent = _is_context_dependent_request(latest["text"])
            contextual_text = _contextual_user_request_text(
                latest_request=latest["text"],
                previous_request=previous["text"],
                context_dependent=context_dependent,
            )
            return {
                "text": latest["text"],
                "timestamp": latest["timestamp"],
                "previous_text": previous["text"],
                "previous_timestamp": previous["timestamp"],
                "is_context_dependent": "yes" if context_dependent else "no",
                "contextual_text": contextual_text,
            }
    fallback = _summary_substantive_user_request(summary)
    return {
        "text": fallback,
        "timestamp": "",
        "previous_text": "",
        "previous_timestamp": "",
        "is_context_dependent": "no",
        "contextual_text": fallback,
    }


def _build_resolved_state(
    *,
    parsed: ParsedSession | None,
    summary: dict[str, Any],
    latest_user_signal: dict[str, str],
    recent_actions: list[str],
    repo_state: dict[str, Any],
    redacted: bool,
    context: RedactionContext,
) -> dict[str, str]:
    latest_user_request = latest_user_signal.get("text", "")
    latest_user_timestamp = latest_user_signal.get("timestamp", "")
    contextual_user_request = latest_user_signal.get("contextual_text", latest_user_request)
    completion_message = _latest_completion_message_after(
        parsed,
        timestamp=latest_user_timestamp,
        redacted=redacted,
        context=context,
    )
    latest_answer = completion_message or _latest_final_answer_after(
        parsed,
        timestamp=latest_user_timestamp,
        redacted=redacted,
        context=context,
    )
    fallback_answer = _string(summary.get("last_assistant_message"))

    if parsed and _has_unresolved_aborted_turn(parsed):
        status = "blocked"
    elif latest_answer and recent_actions:
        status = "handled_with_changes"
    elif latest_answer:
        status = "answered"
    elif parsed is None and fallback_answer:
        status = "derived_only"
    elif latest_user_request:
        status = "unanswered"
    else:
        status = "unknown"

    resolution_summary = latest_answer or fallback_answer
    if redacted:
        resolution_summary = redact_text(resolution_summary, context).text

    return {
        "latest_user_request": latest_user_request,
        "previous_user_request": latest_user_signal.get("previous_text", ""),
        "latest_user_request_is_context_dependent": latest_user_signal.get(
            "is_context_dependent",
            "no",
        ),
        "contextual_user_request": contextual_user_request,
        "request_resolution_status": status,
        "resolution_summary": _excerpt_text(resolution_summary, limit=320),
        "validation_summary": _validation_summary(recent_actions, status),
        "commit_summary": _commit_summary(repo_state),
        "dirty_state_summary": _dirty_state_summary(repo_state),
        "remaining_local_only_paths": "unknown",
    }


def _build_continuation_brief(
    *,
    session_title: str,
    current_state: dict[str, str],
    resolved_state: dict[str, str],
    open_loops: dict[str, str],
    source_available: bool,
) -> dict[str, Any]:
    latest_request = _string(resolved_state.get("latest_user_request"))
    contextual_request = _string(resolved_state.get("contextual_user_request")) or latest_request
    resolution_status = _string(resolved_state.get("request_resolution_status"))
    latest_resolved_request = contextual_request if resolution_status in {
        "answered",
        "handled_with_changes",
        "completed",
        "derived_only",
    } else ""

    evidence = []
    has_resolution = resolution_status in {
        "answered",
        "handled_with_changes",
        "completed",
        "derived_only",
    }
    if source_available:
        evidence.append("Local source session was available for exact recent context.")
    if latest_request:
        evidence.append("Latest substantive user request was extracted from the transcript.")
    if resolved_state.get("latest_user_request_is_context_dependent") == "yes":
        evidence.append(
            "Latest request was context-dependent and expanded with the previous request."
        )
    if has_resolution and resolved_state.get("resolution_summary"):
        evidence.append("Resolution summary comes from the latest final answer or task completion.")
    if open_loops.get("operational_risk") != "none":
        evidence.append(f"Operational risk: {open_loops.get('operational_risk')}")

    return {
        "what_we_were_doing": _excerpt_text(
            current_state.get("current_focus") or contextual_request or session_title,
            limit=220,
        ),
        "why_it_mattered": _why_it_mattered_text(contextual_request),
        "latest_resolved_request": latest_resolved_request,
        "last_meaningful_outcome": _string(current_state.get("last_meaningful_outcome")),
        "next_best_action": _next_best_action_for_brief(
            session_title=session_title,
            current_state=current_state,
            resolved_state=resolved_state,
            open_loops=open_loops,
        ),
        "do_not_do": (
            "Do not treat this as a live provider resume; continue from derived "
            "handoff artifacts only."
        ),
        "confidence": "high" if source_available and resolution_status in {
            "answered",
            "handled_with_changes",
        } else "medium" if source_available else "low",
        "evidence": evidence,
    }


def _build_changed_artifacts(
    *,
    parsed: ParsedSession | None,
    resolved_state: dict[str, str],
    recent_window: list[dict[str, Any]],
    repo_state: dict[str, Any],
    redacted: bool,
    context: RedactionContext,
) -> dict[str, Any]:
    changed_paths: list[dict[str, str]] = []
    key_paths: list[dict[str, str]] = []
    repo_root = _string(repo_state.get("repo_root"))

    if parsed:
        for block in parsed.conversation_entries[-RECENT_ACTION_LOOKBACK:]:
            if block.kind == "tool_output" and "Updated the following files:" in block.text:
                for path in _updated_files_from_tool_output(block.text):
                    resolved_path = _resolve_artifact_path(
                        path,
                        repo_root=repo_root,
                    )
                    _append_artifact(
                        changed_paths,
                        path=resolved_path,
                        source="tool_output_updated_files",
                        status="changed",
                        note="Reported by recent tool output.",
                        redacted=redacted,
                        context=context,
                    )

    for item in _as_list(repo_state.get("repo_dirty_paths")):
        artifact = _as_dict(item)
        _append_artifact(
            changed_paths,
            path=_string(artifact.get("path")),
            source="git_status",
            status=_string(artifact.get("status")) or "dirty",
            note="Repo has this path in git status.",
            redacted=redacted,
            context=context,
        )

    text_sources = [
        _string(resolved_state.get("latest_user_request")),
        _string(resolved_state.get("contextual_user_request")),
        _string(resolved_state.get("resolution_summary")),
    ]
    text_sources.extend(
        _string(item.get("text"))
        for item in recent_window
        if isinstance(item, dict)
    )
    for text in text_sources:
        for path in _path_mentions_from_text(text):
            resolved_path = _resolve_artifact_path(path, repo_root=repo_root)
            _append_artifact(
                key_paths,
                path=resolved_path,
                source="recent_text_path_mention",
                status="referenced",
                note="Mentioned in recent request, response, or summary.",
                redacted=redacted,
                context=context,
            )

    recommended = _recommended_inspection_order(changed_paths, key_paths)
    summary = _changed_artifacts_summary(changed_paths, key_paths, recommended)
    return {
        "summary": summary,
        "changed_paths": changed_paths[:20],
        "key_paths": key_paths[:20],
        "recommended_inspection_order": recommended[:10],
    }


def _append_artifact(
    target: list[dict[str, str]],
    *,
    path: str,
    source: str,
    status: str,
    note: str,
    redacted: bool,
    context: RedactionContext,
) -> None:
    normalized = _normalize_artifact_path(path)
    if not normalized or _artifact_path_seen(target, normalized):
        return
    if redacted:
        normalized = redact_text(normalized, context).text
        note = redact_text(note, context).text
    target.append(
        {
            "path": normalized,
            "source": source,
            "status": status,
            "note": note,
        }
    )


def _artifact_path_seen(items: list[dict[str, str]], path: str) -> bool:
    return any(item.get("path") == path for item in items)


def _path_mentions_from_text(text: str) -> list[str]:
    paths: list[str] = []
    for match in re.finditer(r"\[[^\]]+\]\(([^)]+)\)", text):
        paths.append(match.group(1))
    for match in re.finditer(r"`([^`]*(?:/|\\)[^`]*)`", text):
        paths.append(match.group(1))
    for match in re.finditer(
        r"(?<![\w.-])(?:\.{0,2}/|/)[^\s)\],;:]+(?:\.[A-Za-z0-9_]+)(?::\d+)?",
        text,
    ):
        paths.append(match.group(0))
    return [_normalize_artifact_path(path) for path in paths if _normalize_artifact_path(path)]


def _normalize_artifact_path(path: str) -> str:
    cleaned = path.strip().strip("\"'")
    if "](" in cleaned:
        cleaned = cleaned.rsplit("](", maxsplit=1)[-1]
        cleaned = cleaned.split(")", maxsplit=1)[0]
    if cleaned.startswith("<") and cleaned.endswith(">"):
        cleaned = cleaned[1:-1].strip()
    cleaned = cleaned.replace("\\", "/")
    cleaned = re.sub(r"^file://", "", cleaned)
    cleaned = re.sub(r":\d+(?::\d+)?$", "", cleaned)
    cleaned = cleaned.rstrip(".,;)")
    if cleaned in {"/", "./", "../"}:
        return ""
    if _is_noisy_artifact_path(cleaned):
        return ""
    if not cleaned or cleaned.startswith(("http://", "https://")):
        return ""
    if _looks_like_shell_command_path(cleaned):
        return ""
    if "\n" in cleaned or len(cleaned) > 260:
        return ""
    if re.search(r"\s--?[A-Za-z0-9][\w-]*(?:\s|=)", cleaned):
        return ""
    if "/" not in cleaned and "." not in Path(cleaned).name:
        return ""
    return cleaned


def _resolve_artifact_path(path: str, *, repo_root: str) -> str:
    normalized = _normalize_artifact_path(path)
    if not normalized:
        return normalized
    repo_relative = _repo_relative_artifact_path(normalized, repo_root=repo_root)
    if repo_relative:
        return repo_relative
    if "/" in normalized or "\\" in normalized:
        return normalized
    if not repo_root or not Path(normalized).suffix:
        return normalized

    root = Path(repo_root).expanduser()
    if not root.is_dir():
        return normalized

    matches = _repo_filename_matches(root, normalized)
    if len(matches) != 1:
        return normalized
    best_match = matches[0]
    try:
        return best_match.relative_to(root).as_posix()
    except ValueError:
        return best_match.as_posix()


def _repo_filename_matches(root: Path, filename: str) -> list[Path]:
    ignored_dirs = {
        ".agent-bridge",
        ".codex",
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "node_modules",
        "out",
    }
    matches: list[Path] = []
    for candidate in root.rglob(filename):
        if any(part in ignored_dirs for part in candidate.parts):
            continue
        if candidate.is_file():
            matches.append(candidate)
        if len(matches) >= 25:
            break
    return matches


def _repo_relative_artifact_path(path: str, *, repo_root: str) -> str:
    if not repo_root:
        return ""
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        return ""
    root = Path(repo_root).expanduser()
    try:
        relative = candidate.resolve(strict=False).relative_to(
            root.resolve(strict=False)
        )
    except (OSError, ValueError):
        return ""
    rendered = relative.as_posix()
    return "" if rendered == "." else rendered


def _is_noisy_artifact_path(path: str) -> bool:
    normalized = path.strip().replace("\\", "/")
    if re.fullmatch(r"\d+/\d+", normalized):
        return True
    if "/.cache/starship/" in normalized or normalized.startswith(".cache/starship/"):
        return True
    if "/.cache/" in normalized and re.search(r"/session_\d+\.log$", normalized):
        return True
    return False


def _looks_like_shell_command_path(path: str) -> bool:
    first_token = path.strip().split(maxsplit=1)[0] if path.strip() else ""
    return first_token in {
        "bash",
        "sh",
        "python",
        "python3",
        "uv",
        "pytest",
        "ruff",
        "mypy",
        "workstation",
        "codex-session-handoff",
        "codex-session-mirror",
    }


def _recommended_inspection_order(
    changed_paths: list[dict[str, str]],
    key_paths: list[dict[str, str]],
) -> list[str]:
    ordered: list[str] = []
    qualified_basenames = _qualified_artifact_basenames([*key_paths, *changed_paths])
    for item in [*key_paths, *changed_paths]:
        path = item.get("path", "")
        if not path or path in ordered:
            continue
        if not _is_recommended_artifact_path(path):
            continue
        if _is_bare_artifact_path(path) and Path(path).name in qualified_basenames:
            continue
        ordered.append(path)
    return ordered


def _qualified_artifact_basenames(items: list[dict[str, str]]) -> set[str]:
    basenames: set[str] = set()
    for item in items:
        path = item.get("path", "")
        if "/" in path.replace("\\", "/"):
            name = Path(path.replace("\\", "/")).name
            if name:
                basenames.add(name)
    return basenames


def _is_bare_artifact_path(path: str) -> bool:
    normalized = path.strip().replace("\\", "/")
    return bool(normalized) and "/" not in normalized and "." in Path(normalized).name


def _is_recommended_artifact_path(path: str) -> bool:
    normalized = path.strip().replace("\\", "/")
    if not normalized:
        return False
    if _is_noisy_artifact_path(normalized):
        return False
    if normalized in {".codex", ".agent-bridge", ".agent-bridge/", "workflow", "workflow/"}:
        return False
    if normalized.startswith((".codex/", ".agent-bridge/", "workflow/")):
        return False
    if normalized == "__init__.py":
        return False
    if normalized.endswith(".env") or "/.env" in normalized:
        return False
    return True


def _changed_artifacts_summary(
    changed_paths: list[dict[str, str]],
    key_paths: list[dict[str, str]],
    recommended: list[str],
) -> str:
    if not changed_paths and not key_paths:
        return "No concrete artifact paths were extracted from the recent handoff context."
    return (
        f"Extracted {len(changed_paths)} changed path(s), {len(key_paths)} key "
        f"path(s), and {len(recommended)} recommended inspection target(s)."
    )


def _artifact_markdown_lines(items: list[Any]) -> list[str]:
    if not items:
        return ["- none"]
    lines: list[str] = []
    for item in items:
        artifact = _as_dict(item)
        path = _string(artifact.get("path")) or "unknown"
        status = _string(artifact.get("status")) or "unknown"
        source = _string(artifact.get("source")) or "unknown"
        note = _string(artifact.get("note"))
        suffix = f" - {note}" if note else ""
        lines.append(f"- `{path}` (`{status}`, `{source}`){suffix}")
    return lines


def _build_decisions_and_invariants(
    *,
    parsed: ParsedSession | None,
    continuation_brief: dict[str, Any],
    resolved_state: dict[str, str],
    changed_artifacts: dict[str, Any],
    recent_window: list[dict[str, Any]],
    redacted: bool,
    context: RedactionContext,
) -> dict[str, Any]:
    decisions: list[dict[str, str]] = []
    invariants: list[dict[str, str]] = []
    rejected_paths: list[dict[str, str]] = []
    open_questions: list[dict[str, str]] = []

    sources = [
        ("continuation_brief", _string(continuation_brief.get("what_we_were_doing"))),
        ("resolved_state", _string(resolved_state.get("contextual_user_request"))),
        ("changed_artifacts", _string(changed_artifacts.get("summary"))),
    ]
    if parsed:
        sources.extend(_structural_memory_sources(parsed))
        sources.extend(_review_memory_sources(parsed))
        sources.extend(_implementation_outcome_sources(parsed))
        sources.extend(
            ("recent_window", block.text)
            for block in parsed.conversation_entries[-8:]
            if block.kind in {"user", "assistant"}
        )
    else:
        sources.append(
            (
                "continuation_brief",
                _string(continuation_brief.get("last_meaningful_outcome")),
            )
        )
        sources.append(("resolved_state", _string(resolved_state.get("resolution_summary"))))
        sources.extend(
            ("recent_window", _string(item.get("text")))
            for item in recent_window
            if isinstance(item, dict) and item.get("kind") in {"user", "assistant"}
        )

    for source, text in sources:
        for candidate in _memory_candidates_from_text(text):
            item = _memory_item(
                candidate,
                source=source,
                redacted=redacted,
                context=context,
            )
            if _is_rejected_path(candidate):
                _append_memory_item(rejected_paths, item)
            elif _is_implementation_outcome_decision(candidate):
                _append_memory_item(decisions, item)
            elif _is_open_architecture_question(candidate):
                _append_memory_item(open_questions, item)
            elif _is_invariant(candidate):
                _append_memory_item(invariants, item)
            elif _is_decision(candidate):
                _append_memory_item(decisions, item)

    confidence = "medium"
    if decisions or invariants or rejected_paths:
        confidence = "high"
    if not decisions and not invariants and not rejected_paths and not open_questions:
        confidence = "low"

    return {
        "decisions": decisions[:8],
        "invariants": invariants[:8],
        "rejected_paths": rejected_paths[:8],
        "open_architecture_questions": open_questions[:8],
        "evidence": _memory_evidence(decisions, invariants, rejected_paths, open_questions),
        "confidence": confidence,
    }


def _structural_memory_sources(parsed: ParsedSession) -> list[tuple[str, str]]:
    sources: list[tuple[str, str]] = []
    for block in parsed.context_entries:
        candidates = _structural_memory_candidates_from_text(block.text)
        if candidates:
            sources.append(
                (
                    "context_structural_memory",
                    "\n".join(f"- {candidate}" for candidate in candidates),
                )
            )
    return sources


def _review_memory_sources(parsed: ParsedSession) -> list[tuple[str, str]]:
    sources: list[tuple[str, str]] = []
    for block in parsed.conversation_entries[-RECENT_ACTION_LOOKBACK:]:
        if block.kind not in {"user", "assistant"}:
            continue
        candidates = _review_memory_candidates_from_text(block.text)
        if candidates:
            sources.append(
                (
                    "review_memory",
                    "\n".join(f"- {candidate}" for candidate in candidates),
                )
            )
    return sources


def _implementation_outcome_sources(parsed: ParsedSession) -> list[tuple[str, str]]:
    sources: list[tuple[str, str]] = []
    for block in parsed.conversation_entries[-RECENT_ACTION_LOOKBACK:]:
        if block.kind != "assistant":
            continue
        candidates = _implementation_outcome_candidates_from_text(block.text)
        if candidates:
            sources.append(
                (
                    "implementation_outcome",
                    "\n".join(f"- {candidate}" for candidate in candidates),
                )
            )
    return sources


def _implementation_outcome_candidates_from_text(text: str) -> list[str]:
    if not _has_implementation_outcome_signal(text):
        return []

    candidates: list[str] = []
    active_label = ""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        heading = _implementation_outcome_heading(line)
        if heading == "__skip__":
            active_label = ""
            continue
        if heading:
            active_label = heading
            continue

        if line.startswith("#"):
            active_label = ""
            continue

        first_line_candidate = _implementation_outcome_first_line_candidate(line)
        if first_line_candidate:
            candidates.append(first_line_candidate)
            continue

        if not active_label:
            continue
        list_item = _structural_list_item(line)
        if not list_item:
            continue

        candidate = _implementation_outcome_candidate(active_label, list_item)
        if candidate:
            candidates.append(candidate)

    return candidates[:48]


def _has_implementation_outcome_signal(text: str) -> bool:
    lowered = text.lower()
    if (
        "continue from a local extractive handoff" in lowered
        or "first response contract" in lowered
    ):
        return False
    markers = (
        "implemented",
        "implementado",
        "implementada",
        "committed",
        "behavior now",
        "what changed",
        "que suma",
        "qué suma",
        "que quedo",
        "qué quedó",
        "que cambio",
        "qué cambió",
        "changed:",
        "known caveat",
        "caveat:",
        "not implemented",
        "not included",
        "follow-up",
        "remaining",
    )
    return any(marker in lowered for marker in markers)


def _implementation_outcome_heading(line: str) -> str:
    stripped = line.strip()
    looks_like_heading = stripped.startswith("#") or (
        stripped.endswith(":") and not _is_memory_bullet_line(stripped)
    )
    if not looks_like_heading and not (
        stripped.startswith("**") and stripped.endswith("**")
    ):
        return ""
    cleaned = stripped.strip("# ").strip()
    cleaned = re.sub(r"^\*\*|\*\*$", "", cleaned).strip()
    cleaned = cleaned.rstrip(":").strip()
    lowered = cleaned.lower()
    accepted = {
        "behavior now": "Behavior now",
        "what changed": "What changed",
        "que suma": "What changed",
        "qué suma": "What changed",
        "que cambio": "What changed",
        "qué cambió": "What changed",
        "que quedo": "Behavior now",
        "qué quedó": "Behavior now",
        "contract": "Contract",
        "known caveat": "Known caveat",
        "caveat": "Known caveat",
        "remaining": "Remaining",
        "follow-up": "Follow-up",
        "follow up": "Follow-up",
        "not implemented": "Not implemented",
        "not included": "Not included",
    }
    if lowered in accepted:
        return accepted[lowered]
    if lowered in {
        "changed",
        "changes",
        "validation",
        "validated",
        "validacion",
        "validación",
        "tests",
    }:
        return "__skip__"
    if looks_like_heading:
        return "__skip__"
    return ""


def _implementation_outcome_first_line_candidate(line: str) -> str:
    cleaned = line.strip()
    if _is_memory_bullet_line(cleaned):
        return ""
    lowered = cleaned.lower()
    if not lowered.startswith(
        (
            "implemented ",
            "implemented and ",
            "implemente ",
            "implementé ",
            "added ",
            "agregue ",
            "agregué ",
            "updated ",
            "actualice ",
            "actualicé ",
            "fixed ",
            "corregi ",
            "corregí ",
            "hardened ",
            "created ",
            "committed ",
        )
    ):
        return ""
    if _looks_like_validation_line(cleaned):
        return ""
    return _excerpt_text(f"Implementation outcome: {cleaned}", limit=240)


def _implementation_outcome_candidate(label: str, text: str) -> str:
    cleaned = text.strip()
    if not cleaned or _looks_like_validation_line(cleaned):
        return ""
    if label in {"Changed", "Changes"} and _looks_like_path_only_item(cleaned):
        return ""
    return _excerpt_text(f"{label}: {cleaned}", limit=240)


def _looks_like_validation_line(text: str) -> bool:
    lowered = text.lower().strip()
    return lowered.startswith(
        ("ran ", "validation:", "validated:", "validacion:", "validación:")
    ) or any(
        marker in lowered
        for marker in (
            "pytest",
            "ruff check",
            "mypy",
            "all checks passed",
        )
    )


def _looks_like_path_only_item(text: str) -> bool:
    cleaned = text.strip().strip("`")
    if not cleaned:
        return False
    if " " in cleaned:
        return False
    return "/" in cleaned or "." in Path(cleaned).name


def _review_memory_candidates_from_text(text: str) -> list[str]:
    if not _has_review_memory_signal(text):
        return []

    candidates: list[str] = []
    active_label = ""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        heading = _review_memory_heading(line)
        if heading:
            active_label = heading
            continue

        if line.startswith("#"):
            active_label = ""
            continue

        if not active_label:
            continue

        list_item = _structural_list_item(line)
        if not list_item:
            continue

        candidate = _review_memory_candidate(active_label, list_item)
        if candidate and _has_memory_signal(candidate):
            candidates.append(candidate)

    return candidates[:48]


def _has_review_memory_signal(text: str) -> bool:
    lowered = text.lower()
    if (
        "continue from a local extractive handoff" in lowered
        or "first response contract" in lowered
    ):
        return False
    markers = (
        "findings",
        "resolved during review",
        "residual risks",
        "residual risk",
        "residual test gaps",
        "open questions",
        "recommendation",
        "recommended next step",
        "blockers",
    )
    return any(marker in lowered for marker in markers)


def _review_memory_heading(line: str) -> str:
    stripped = line.strip()
    looks_like_heading = stripped.startswith("#") or (
        stripped.endswith(":") and not _is_memory_bullet_line(stripped)
    )
    if not looks_like_heading and not (
        stripped.startswith("**") and stripped.endswith("**")
    ):
        return ""
    cleaned = stripped.strip("# ").strip()
    cleaned = re.sub(r"^\*\*|\*\*$", "", cleaned).strip()
    cleaned = cleaned.rstrip(":").strip()
    lowered = cleaned.lower()
    accepted = (
        "findings",
        "resolved during review",
        "notes",
        "residual risks",
        "residual risk",
        "residual test gaps",
        "open questions",
        "recommendation",
        "recommended next step",
        "blockers",
    )
    if lowered in accepted:
        return cleaned
    return ""


def _review_memory_candidate(label: str, text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return ""
    return _excerpt_text(f"{label}: {cleaned}", limit=240)


def _structural_memory_candidates_from_text(text: str) -> list[str]:
    if not _has_structural_memory_signal(text):
        return []

    candidates: list[str] = []
    active_label = ""
    parent_item = ""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        is_nested_item = raw_line.startswith((" ", "\t"))

        heading = _structural_memory_heading(line)
        if heading:
            active_label = heading
            parent_item = ""
            continue

        if line.startswith("#"):
            active_label = ""
            parent_item = ""
            continue

        list_item = _structural_list_item(line)
        if not list_item:
            continue
        if not active_label:
            continue

        if parent_item and not is_nested_item:
            parent_item = ""

        if _line_introduces_nested_list(list_item):
            parent_item = list_item.rstrip(":")
            continue
        elif parent_item and is_nested_item:
            candidate = _structural_candidate(active_label, f"{parent_item}: {list_item}")
        else:
            candidate = _structural_candidate(active_label, list_item)

        if candidate and _has_memory_signal(candidate):
            candidates.append(candidate)

    return candidates[:64]


def _has_structural_memory_signal(text: str) -> bool:
    lowered = text.lower()
    if (
        "continue from a local extractive handoff" in lowered
        or "first response contract" in lowered
    ):
        return False
    markers = (
        "strategic decisions already made",
        "stable boundary",
        "product identity",
        "current intended identity",
        "repo boundaries",
        "public boundary",
        "support matrix",
        "source of truth",
        "non-goals",
        "non-goals",
        "ownership",
        "does not own",
        "do not want",
        "explicitly chose",
    )
    return any(marker in lowered for marker in markers)


def _structural_memory_heading(line: str) -> str:
    stripped = line.strip()
    looks_like_heading = stripped.startswith("#") or (
        stripped.endswith(":") and not _is_memory_bullet_line(stripped)
    )
    if not looks_like_heading:
        return ""
    cleaned = line.strip().strip("# ").strip()
    cleaned = cleaned.rstrip(":").strip()
    lowered = cleaned.lower()
    accepted = (
        "strategic decisions already made",
        "stable boundary",
        "product identity",
        "current intended identity",
        "current state",
        "important caveat",
        "known risks",
        "what it does not do",
        "what does not do",
        "non-goals",
        "non-goals",
    )
    if lowered in accepted:
        return cleaned
    if lowered.endswith("boundary") or lowered.endswith("ownership"):
        return cleaned
    return ""


def _structural_list_item(line: str) -> str:
    cleaned = re.sub(r"^(?:[-•*]|\d+[.)])\s+", "", line).strip()
    if cleaned == line and not re.match(r"^\d+[.)]\s+", line):
        return ""
    return cleaned


def _line_introduces_nested_list(line: str) -> bool:
    lowered = line.lower()
    return line.endswith(":") or lowered.endswith("does not own")


def _structural_candidate(label: str, text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return ""
    if label:
        cleaned = f"{label}: {cleaned}"
    return _excerpt_text(cleaned, limit=240)


def _memory_candidates_from_text(text: str) -> list[str]:
    segments = _memory_text_segments(_strip_memory_ide_wrapper(text))
    if not segments:
        return []
    candidates: list[str] = []
    for segment in segments:
        for part in _memory_segment_parts(segment):
            cleaned = _clean_memory_statement(part)
            if not cleaned:
                continue
            if len(cleaned) < 24 or len(cleaned) > 260:
                continue
            if _has_memory_signal(cleaned):
                candidates.append(cleaned)
    return candidates


def _memory_text_segments(text: str) -> list[str]:
    segments: list[str] = []
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            segments.append(" ".join(paragraph))
            paragraph.clear()

    for raw_line in text.strip().splitlines():
        line = raw_line.strip()
        if not line:
            flush_paragraph()
            continue
        if _is_memory_bullet_line(line):
            flush_paragraph()
            segments.append(line)
            continue
        paragraph.append(line)
    flush_paragraph()
    return segments


def _memory_segment_parts(segment: str) -> list[str]:
    normalized = " ".join(segment.strip().split())
    if not normalized:
        return []
    normalized = re.sub(r"^(?:[-•*]|\d+[.)])\s+", "", normalized)
    return re.split(r"(?<=[.!?])\s+", normalized)


def _is_memory_bullet_line(line: str) -> bool:
    return re.match(r"^(?:[-•*]|\d+[.)])\s+", line) is not None


def _clean_memory_statement(text: str) -> str:
    cleaned = text.strip().strip("-•* ")
    cleaned = re.sub(r"^\*\*[^*]+\*\*\s*", "", cleaned)
    cleaned = re.sub(r"^Sum\s+\d+:\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", cleaned)
    cleaned = cleaned.replace("**", "")
    cleaned = cleaned.strip().strip("\"'")
    lowered = cleaned.lower()
    if "exact validation" in lowered or "validation commands" in lowered:
        return ""
    if _looks_like_validation_line(cleaned):
        return ""
    if lowered.startswith(("si querés", "si queres", "if you want")):
        return ""
    if cleaned.endswith(":") and len(cleaned) < 120:
        return ""
    return _excerpt_text(cleaned, limit=240)


def _strip_memory_ide_wrapper(text: str) -> str:
    stripped = text.strip()
    marker_match = re.search(r"#{0,6}\s*My request for Codex:\s*", stripped)
    if marker_match:
        return stripped[marker_match.end() :].strip()
    if "# Context from my IDE setup" not in stripped and "## Open tabs:" not in stripped:
        return stripped

    filtered_lines: list[str] = []
    skip_open_tabs = False
    for raw_line in stripped.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lowered = line.lower()
        if lowered.startswith("# context from my ide setup"):
            continue
        if lowered.startswith("## active file:"):
            continue
        if lowered.startswith("## open tabs:"):
            skip_open_tabs = True
            continue
        if skip_open_tabs:
            if line.startswith("-"):
                continue
            if line.startswith("#"):
                skip_open_tabs = False
            else:
                continue
        filtered_lines.append(raw_line)
    return "\n".join(filtered_lines).strip()


def _has_memory_signal(text: str) -> bool:
    lowered = text.lower()
    markers = (
        "prueba que",
        "valida",
        "aprendimos",
        "candidate supply",
        "lane",
        "separada",
        "separado",
        "rescue",
        "no deployable",
        "no como solución",
        "no como solucion",
        "no promover",
        "no mezclar",
        "score",
        "siguiente paso",
        "next step",
        "faltaba",
        "limitado",
        "limited",
        "arquitectura",
        "infrastructure",
        "retrieval",
        "hypothesis",
        "hipótesis",
        "hipotesis",
        "strategic decisions",
        "stable boundary",
        "product identity",
        "source of truth",
        "public boundary",
        "support matrix",
        "repo-owned",
        "ownership",
        "does not own",
        "workflow truth",
        "provider/session/thread",
        "transport/control",
        "explicitly chose",
        "new repo",
        "do not want",
        "no workflow runtime",
        "no workstation continuity ownership",
        "no daemon",
        "no polling",
        "no slack truth",
        "fail-closed",
        "fail closed",
        "findings",
        "finding",
        "residual risk",
        "residual risks",
        "residual test gap",
        "residual test gaps",
        "open questions",
        "recommendation",
        "recommended next step",
        "blocker",
        "blockers",
        "overclaiming",
        "corrupt",
        "malformed",
        "retry",
        "coverage",
        "should probably",
        "public docs",
        "conflict",
        "implementation outcome",
        "behavior now",
        "what changed",
        "contract:",
        "known caveat",
        "not implemented",
        "not included",
        "follow-up:",
        "remaining",
    )
    return any(marker in lowered for marker in markers)


def _memory_item(
    statement: str,
    *,
    source: str,
    redacted: bool,
    context: RedactionContext,
) -> dict[str, str]:
    rendered = redact_text(statement, context).text if redacted else statement
    return {
        "statement": rendered,
        "source": source,
        "confidence": "medium",
    }


def _append_memory_item(target: list[dict[str, str]], item: dict[str, str]) -> None:
    statement = item.get("statement", "")
    normalized = _normalize_for_matching(statement)
    if not normalized:
        return
    for existing in target:
        existing_statement = _normalize_for_matching(existing.get("statement", ""))
        if normalized == existing_statement:
            return
        if normalized in existing_statement or existing_statement in normalized:
            return
    target.append(item)


def _is_decision(text: str) -> bool:
    lowered = text.lower()
    markers = (
        "prueba que",
        "valida",
        "aprendimos",
        "implemented",
        "added",
        "chose",
        "chosen",
        "explicitly chose",
        "decided",
        "decision",
        "validated",
        "validation passed",
        "funcionó",
        "funciono",
        "smoke",
        "siguiente paso",
        "next step",
        "conviene",
        "lo haría",
        "lo haria",
        "recommendation",
        "recommended next step",
        "resolved during review",
        "implementation outcome",
        "behavior now",
        "what changed",
    )
    return any(marker in lowered for marker in markers)


def _is_invariant(text: str) -> bool:
    lowered = text.lower()
    markers = (
        "candidate supply",
        "lane",
        "separada",
        "separado",
        "rescue gate",
        "arquitectura",
        "architecture",
        "stable boundary",
        "product identity",
        "source of truth",
        "public boundary",
        "support matrix",
        "repo-owned",
        "ownership",
        "workflow truth",
        "transport/control",
        "no workflow runtime",
        "no workstation continuity ownership",
        "no daemon",
        "no polling",
        "no slack truth",
        "fail-closed",
        "fail closed",
        "debe",
        "must",
        "read-only",
        "dirty repo",
        "no tocar",
        "no revert",
        "sin promoción",
        "sin promocion",
        "contract:",
    )
    return any(marker in lowered for marker in markers)


def _is_rejected_path(text: str) -> bool:
    lowered = text.lower()
    negative_markers = (
        "no deployable",
        "not deployable",
        "no como solución",
        "no como solucion",
        "no promover",
        "no mezclar",
        "should not live",
        "should not",
        "must not",
        "do not want to depend",
        "not replace it",
        "sin promoción automática",
        "sin promocion automatica",
        "not implemented",
        "not included",
    )
    return any(marker in lowered for marker in negative_markers)


def _is_open_architecture_question(text: str) -> bool:
    lowered = text.lower()
    if "?" in text:
        return True
    markers = (
        "siguiente paso",
        "next step",
        "queda pendiente",
        "queda por",
        "todavía queda",
        "todavia queda",
        "pending",
        "pendiente",
        "habría que",
        "habria que",
        "finding",
        "findings",
        "residual risk",
        "residual risks",
        "residual test gap",
        "residual test gaps",
        "open question",
        "open questions",
        "blocker",
        "blockers",
        "risk",
        "gap",
        "missing",
        "should probably",
        "corrupt",
        "malformed",
        "known caveat",
        "caveat",
        "follow-up:",
        "remaining",
    )
    return any(marker in lowered for marker in markers)


def _is_implementation_outcome_decision(text: str) -> bool:
    lowered = text.lower()
    return lowered.startswith(
        (
            "implementation outcome:",
            "behavior now:",
            "what changed:",
        )
    )


def _memory_evidence(*groups: list[dict[str, str]]) -> list[str]:
    sources: list[str] = []
    for group in groups:
        for item in group:
            source = item.get("source", "")
            if source and source not in sources:
                sources.append(source)
    return [f"Extracted from {source}." for source in sources]


def _memory_markdown_lines(items: list[Any]) -> list[str]:
    if not items:
        return ["- none"]
    lines: list[str] = []
    for item in items:
        memory = _as_dict(item)
        statement = _string(memory.get("statement")) or _string(item)
        source = _string(memory.get("source")) or "unknown"
        confidence = _string(memory.get("confidence")) or "unknown"
        lines.append(f"- {statement} (`{source}`, `{confidence}`)")
    return lines


def _build_restart_prompt(
    *,
    session_id: str,
    session_title: str,
    artifacts: dict[str, Any],
    continuation_brief: dict[str, Any],
    resolved_state: dict[str, str],
    open_loops: dict[str, str],
    reentry_posture: dict[str, Any],
    changed_artifacts: dict[str, Any],
    decisions_and_invariants: dict[str, Any],
    linked_child_sessions: list[dict[str, str]],
) -> dict[str, str]:
    repo_state = (
        "clean"
        if artifacts.get("repo_clean") is True
        else "dirty"
        if artifacts.get("repo_clean") is False
        else "unknown"
    )
    child_lines = _restart_prompt_child_lines(linked_child_sessions)
    contract_lines = [
        f"- {item}"
        for item in _as_list(reentry_posture.get("first_turn_contract"))
    ]
    inspection_lines = _restart_prompt_path_lines(
        _as_list(changed_artifacts.get("recommended_inspection_order"))
    )
    decision_lines = _restart_prompt_memory_lines(
        _as_list(decisions_and_invariants.get("decisions")),
        fallback="none",
    )
    invariant_lines = _restart_prompt_memory_lines(
        _as_list(decisions_and_invariants.get("invariants")),
        fallback="none",
    )
    rejected_lines = _restart_prompt_memory_lines(
        _as_list(decisions_and_invariants.get("rejected_paths")),
        fallback="none",
    )
    open_question_lines = _restart_prompt_memory_lines(
        _as_list(decisions_and_invariants.get("open_architecture_questions")),
        fallback="none",
    )
    text_lines = [
        "Continue from a local extractive handoff. Do not treat this as a live provider resume.",
        "Initial operating mode: read-only context retrieval and review only.",
        (
            "Do not run commands, inspect files, edit files, create files, or "
            "run tests in the first response."
        ),
        (
            "Before taking action, ask the user to confirm the desired mode: "
            "review, plan, or implement."
        ),
        "",
        f"Session: {session_title or session_id}",
        f"Session ID: {session_id}",
        f"Repo root: {artifacts.get('repo_root') or 'n/a'}",
        f"Branch: {artifacts.get('repo_branch') or 'n/a'}",
        f"HEAD: {artifacts.get('repo_head_commit') or 'n/a'}",
        f"Repo state: {repo_state}",
        "",
        "Re-entry posture:",
        f"- Role hint: {reentry_posture.get('role_hint') or 'unknown'}",
        f"- Initial mode: {reentry_posture.get('initial_mode') or 'unknown'}",
        "- Requires confirmation before changes: yes",
        "",
        "First response contract:",
        *contract_lines,
        "",
        "Required first response format:",
        "1. Recovered context: summarize the session, repo, state, resolved outcome, "
        "and next best action using only this prompt.",
        "2. Prior posture: state the role hint, initial mode, and confirmation requirement.",
        "3. Candidate next steps if confirmed: list what you would do in `review`, "
        "`plan`, and `implement` mode.",
        "4. Confirmation question: ask exactly one concise question asking the user "
        "to choose `review`, `plan`, or `implement`.",
        "Do not skip any section, even when the handoff looks complete or minimal.",
        "",
        "Continuation brief:",
        f"- What we were doing: {continuation_brief.get('what_we_were_doing') or 'n/a'}",
        f"- Latest resolved request: {continuation_brief.get('latest_resolved_request') or 'n/a'}",
        f"- Last meaningful outcome: {continuation_brief.get('last_meaningful_outcome') or 'n/a'}",
        f"- Next best action: {continuation_brief.get('next_best_action') or 'n/a'}",
        "",
        "Resolved state:",
        f"- Latest user request: {resolved_state.get('latest_user_request') or 'n/a'}",
        f"- Contextual user request: {resolved_state.get('contextual_user_request') or 'n/a'}",
        f"- Resolution status: {resolved_state.get('request_resolution_status') or 'unknown'}",
        f"- Resolution summary: {resolved_state.get('resolution_summary') or 'n/a'}",
        f"- Validation summary: {resolved_state.get('validation_summary') or 'n/a'}",
        f"- Dirty state summary: {resolved_state.get('dirty_state_summary') or 'n/a'}",
        "",
        "Changed / key artifacts:",
        f"- Summary: {changed_artifacts.get('summary') or 'n/a'}",
        "- Recommended inspection order:",
        *inspection_lines,
        "",
        "Decisions and invariants:",
        "- Decisions:",
        *decision_lines,
        "- Invariants:",
        *invariant_lines,
        "- Rejected paths:",
        *rejected_lines,
        "- Open questions / risks:",
        *open_question_lines,
        "",
        "Open loops and risks:",
        f"- Pending validation: {open_loops.get('pending_validation') or 'none'}",
        f"- Open question: {open_loops.get('open_question') or 'none'}",
        f"- Unresolved failure: {open_loops.get('unresolved_failure') or 'none'}",
        f"- Operational risk: {open_loops.get('operational_risk') or 'none'}",
        "",
        "Linked child sessions:",
        *child_lines,
        "",
        "Artifact links:",
        f"- Handoff Markdown: {artifacts.get('handoff_markdown_relpath') or 'n/a'}",
        f"- Handoff JSON: {artifacts.get('handoff_json_relpath') or 'n/a'}",
        f"- Transcript: {artifacts.get('markdown_relpath') or 'n/a'}",
        f"- Reader: {artifacts.get('reader_relpath') or 'n/a'}",
        "",
        (
            "First action: answer with the First response contract and Required "
            "first response format only, then wait for user confirmation before "
            "using tools or changing files."
        ),
    ]
    text = "\n".join(text_lines)
    return {
        "kind": "fresh_session_reentry",
        "text": _excerpt_text(text, limit=8000),
    }


def _restart_prompt_path_lines(paths: list[Any]) -> list[str]:
    if not paths:
        return ["  - none"]
    return [f"  - {_string(path)}" for path in paths[:8]]


def _restart_prompt_memory_lines(items: list[Any], *, fallback: str) -> list[str]:
    if not items:
        return [f"  - {fallback}"]
    lines: list[str] = []
    for item in items[:5]:
        memory = _as_dict(item)
        statement = _string(memory.get("statement")) or _string(item)
        if statement:
            lines.append(f"  - {statement}")
    return lines or [f"  - {fallback}"]


def _build_reentry_posture(
    *,
    continuation_brief: dict[str, Any],
    resolved_state: dict[str, str],
    decisions_and_invariants: dict[str, Any],
) -> dict[str, Any]:
    memory_hints = _reentry_memory_hints(decisions_and_invariants)
    haystack = " ".join(
        (
            _string(continuation_brief.get("what_we_were_doing")),
            _string(continuation_brief.get("last_meaningful_outcome")),
            _string(resolved_state.get("latest_user_request")),
            _string(resolved_state.get("contextual_user_request")),
            _string(resolved_state.get("resolution_summary")),
            *memory_hints,
        )
    ).lower()
    role_hint = (
        "architect_reviewer"
        if _looks_like_review_posture(haystack)
        else "operator_reviewer"
    )
    return {
        "role_hint": role_hint,
        "initial_mode": "read_only_context_retrieval",
        "requires_confirmation_before_changes": True,
        "allowed_first_turn_actions": [
            "summarize_recovered_context",
            "infer_prior_session_posture",
            "list_candidate_next_steps",
            "ask_user_to_confirm_mode",
        ],
        "forbidden_first_turn_actions": [
            "run_commands",
            "inspect_files",
            "edit_files",
            "create_files",
            "run_tests",
            "start_implementation",
        ],
        "first_turn_contract": [
            "Do not use tools or inspect files in the first response.",
            "Do not implement, edit, create files, or run tests in the first response.",
            "Summarize the recovered context from this prompt.",
            "State the inferred prior-session role/posture.",
            "List the next steps you would take if confirmed.",
            "Ask the user to choose one mode before acting: review, plan, or implement.",
            "Use the required first response format in the restart prompt; do not collapse "
            "the response to only a mode question.",
        ],
    }


def _reentry_memory_hints(decisions_and_invariants: dict[str, Any]) -> list[str]:
    hints: list[str] = []
    for key in (
        "decisions",
        "invariants",
        "rejected_paths",
        "open_architecture_questions",
    ):
        for item in _as_list(decisions_and_invariants.get(key)):
            memory = _as_dict(item)
            hint = _string(memory.get("statement")) or _string(item)
            if hint:
                hints.append(hint)
    return hints


def _looks_like_review_posture(text: str) -> bool:
    markers = (
        "summary",
        "summaries",
        "review",
        "reviewer",
        "architect",
        "arquitect",
        "qué aprendimos",
        "que aprendimos",
        "conceptualmente",
        "arquitectura",
        "architecture",
        "boundary",
        "boundaries",
        "ownership",
        "stable boundary",
        "public boundary",
        "no como solución deployable",
        "no como solucion deployable",
        "sirve como prueba",
        "agente nuevo",
        "subagents",
        "prompt",
        "hipótesis",
        "hipotesis",
    )
    return any(marker in text for marker in markers)


def _restart_prompt_child_lines(
    linked_child_sessions: list[dict[str, str]],
) -> list[str]:
    if not linked_child_sessions:
        return ["- none"]
    lines: list[str] = []
    for child in linked_child_sessions[:5]:
        title = child.get("title") or child.get("child_session_id") or "Untitled child"
        status = child.get("status") or "unknown"
        session_id = child.get("child_session_id") or "unknown"
        lines.append(f"- {title} ({session_id}, {status})")
    return lines


def _why_it_mattered_text(latest_request: str) -> str:
    if not latest_request:
        return "The handoff needs to preserve the latest working context for re-entry."
    return _excerpt_text(
        f"The latest request needed a continuation path for: {latest_request}",
        limit=260,
    )


def _contextual_user_request_text(
    *,
    latest_request: str,
    previous_request: str,
    context_dependent: bool,
) -> str:
    if not context_dependent or not previous_request:
        return latest_request
    return _excerpt_text(
        f"{previous_request} Follow-up request: {latest_request}",
        limit=360,
    )


def _is_context_dependent_request(text: str) -> bool:
    normalized = _normalize_for_matching(text)
    if not normalized:
        return False
    if normalized in {
        "pasamelo",
        "pasalo",
        "pasame eso",
        "pasame el prompt",
        "pasame la prompt",
        "mandamelo",
        "mandalo",
        "eso",
        "ese",
        "esa",
        "esa opcion",
        "esa opción",
        "ese camino",
        "lo anterior",
        "lo de arriba",
        "el prompt",
        "la prompt",
    }:
        return True
    if any(
        normalized.startswith(prefix)
        for prefix in (
            "pasamelo ",
            "pasalo ",
            "pasame ",
            "mandamelo ",
            "mandalo ",
            "hacelo ",
            "hagamos eso",
        )
    ):
        return True
    words = normalized.split()
    if len(words) > 6 or len(normalized) > 80:
        return False
    return False


def _normalize_for_matching(text: str) -> str:
    replacements = str.maketrans(
        {
            "á": "a",
            "é": "e",
            "í": "i",
            "ó": "o",
            "ú": "u",
            "ü": "u",
            "Á": "a",
            "É": "e",
            "Í": "i",
            "Ó": "o",
            "Ú": "u",
            "Ü": "u",
        }
    )
    lowered = text.strip().lower().translate(replacements)
    lowered = re.sub(r"[¿?¡!.,;:]+", "", lowered)
    return " ".join(lowered.split())


def _next_best_action_for_brief(
    *,
    session_title: str = "",
    current_state: dict[str, str],
    resolved_state: dict[str, str],
    open_loops: dict[str, str],
    changed_artifacts: dict[str, Any] | None = None,
    decisions_and_invariants: dict[str, Any] | None = None,
) -> str:
    if open_loops.get("unresolved_failure") != "none":
        return "Inspect the unresolved failure before making further changes."
    expected_next_command = _string(open_loops.get("expected_next_command"))
    if expected_next_command and expected_next_command != "none":
        return f"Run `{expected_next_command}` or resolve why it is still pending."

    minimal_action = _minimal_reentry_action(
        session_title=session_title,
        current_state=current_state,
        resolved_state=resolved_state,
    )
    if minimal_action:
        return minimal_action

    resolution_status = resolved_state.get("request_resolution_status")
    resolved_follow_up = resolution_status in {"answered", "handled_with_changes", "completed"}
    memory_action = _specific_next_action_from_memory(decisions_and_invariants or {})
    artifact_action = _specific_next_action_from_artifacts(
        changed_artifacts or {},
        resolved_follow_up=resolved_follow_up,
    )
    if resolved_follow_up:
        if memory_action:
            return memory_action
        if artifact_action:
            return artifact_action
    elif memory_action:
        return memory_action
    elif artifact_action:
        return artifact_action
    if resolution_status == "answered":
        return (
            "Continue from the resolution summary and decide the next concrete "
            "implementation or analysis step."
        )
    return _string(current_state.get("next_recommended_action"))


def _minimal_reentry_action(
    *,
    session_title: str,
    current_state: dict[str, str],
    resolved_state: dict[str, str],
) -> str:
    haystack = " ".join(
        (
            session_title,
            _string(current_state.get("current_focus")),
            _string(current_state.get("last_meaningful_outcome")),
            _string(resolved_state.get("latest_user_request")),
            _string(resolved_state.get("contextual_user_request")),
            _string(resolved_state.get("resolution_summary")),
        )
    ).lower()
    if _looks_like_bootstrap_or_ack_request(haystack):
        return (
            "This was a bootstrap/ACK session; no substantive continuation is "
            "expected unless the user asks for follow-up work."
        )
    if _looks_like_transport_initialization_request(haystack):
        return (
            "This was a transport initialization or smoke-test session; continue "
            "only if the user asks for a concrete follow-up."
        )
    return ""


def _looks_like_bootstrap_or_ack_request(text: str) -> bool:
    markers = (
        "bootstrap",
        "acknowledge readiness",
        "reply exactly",
        "respond exactly",
        "readiness for dispatch",
        "bootstrap_ok",
        "_bootstrap_ok",
    )
    return any(marker in text for marker in markers)


def _looks_like_transport_initialization_request(text: str) -> bool:
    markers = (
        "transport test",
        "bounded agent-bridge",
        "agent-bridge turn",
        "app server thread",
        "sync-bound-thread",
        "handshake",
        "smoke test",
    )
    return any(marker in text for marker in markers)


def _specific_next_action_from_memory(decisions_and_invariants: dict[str, Any]) -> str:
    open_items = _prioritized_open_memory_items(
        _as_list(decisions_and_invariants.get("open_architecture_questions"))
    )
    for item in open_items:
        statement = _memory_statement_for_action(item)
        if statement:
            return _excerpt_text(
                "Address the leading open risk or question before taking a new "
                f"implementation step: {statement}",
                limit=320,
            )

    for item in _as_list(decisions_and_invariants.get("decisions")):
        memory = _as_dict(item)
        statement = _memory_statement_for_action(item)
        raw_statement = _string(memory.get("statement")) or _string(item)
        source = _string(memory.get("source"))
        lowered = f"{raw_statement} {statement}".lower()
        if not statement:
            continue
        if source == "implementation_outcome" and not lowered.startswith(
            ("recommendation:", "recommended next step:")
        ):
            continue
        if any(
            marker in lowered
            for marker in (
                "recommendation",
                "recommended next step",
                "next step",
                "siguiente paso",
                "validate ",
                "review ",
                "inspect ",
            )
        ):
            return _excerpt_text(
                f"Continue from the captured recommendation: {statement}",
                limit=320,
            )
    return ""


def _prioritized_open_memory_items(items: list[Any]) -> list[Any]:
    priority: list[Any] = []
    remaining: list[Any] = []
    for item in items:
        memory = _as_dict(item)
        statement = _string(memory.get("statement")) or _string(item)
        source = _string(memory.get("source"))
        lowered = statement.lower()
        if source == "implementation_outcome" or any(
            marker in lowered
            for marker in (
                "known caveat",
                "residual risk",
                "residual risks",
                "blocker",
                "remaining",
            )
        ):
            priority.append(item)
        else:
            remaining.append(item)
    return [*priority, *remaining]


def _specific_next_action_from_artifacts(
    changed_artifacts: dict[str, Any],
    *,
    resolved_follow_up: bool,
) -> str:
    paths = _next_action_artifact_paths(changed_artifacts)
    if not paths:
        return ""
    rendered_paths = _action_path_list(paths[:3])
    if not rendered_paths:
        return ""
    suffix = (
        "continue the scoped follow-up from the resolved state."
        if resolved_follow_up
        else (
            "recover the current unresolved state before choosing review, "
            "plan, or implement."
        )
    )
    return _excerpt_text(
        f"Inspect {rendered_paths} first, then {suffix}",
        limit=320,
    )


def _next_action_artifact_paths(changed_artifacts: dict[str, Any]) -> list[str]:
    key_paths = _as_list(changed_artifacts.get("key_paths"))
    changed_paths = _as_list(changed_artifacts.get("changed_paths"))
    preferred_items = [
        item
        for item in [*key_paths, *changed_paths]
        if _as_dict(item).get("source") != "git_status"
    ]
    fallback_items = [*key_paths, *changed_paths]
    paths = _artifact_paths_from_items(preferred_items)
    if paths:
        return paths[:3]
    return _artifact_paths_from_items(fallback_items)[:3]


def _artifact_paths_from_items(items: list[Any]) -> list[str]:
    paths: list[str] = []
    for raw_item in items:
        item = _as_dict(raw_item)
        path = _string(item.get("path"))
        if not path or path in paths:
            continue
        if not _is_recommended_artifact_path(path):
            continue
        paths.append(path)
    return paths


def _memory_statement_for_action(item: Any) -> str:
    memory = _as_dict(item)
    statement = _string(memory.get("statement")) or _string(item)
    statement = _strip_action_memory_label(statement)
    return _excerpt_text(statement, limit=260) if statement else ""


def _strip_action_memory_label(statement: str) -> str:
    cleaned = statement.strip()
    label, separator, rest = cleaned.partition(":")
    if not separator:
        return cleaned
    accepted_labels = {
        "findings",
        "finding",
        "residual risks",
        "residual risk",
        "residual test gaps",
        "open questions",
        "open question",
        "recommendation",
        "recommended next step",
        "blockers",
        "blocker",
        "known risks",
        "known caveat",
        "important caveat",
    }
    if label.strip().lower() in accepted_labels and rest.strip():
        return rest.strip()
    return cleaned


def _action_path_list(paths: list[str]) -> str:
    cleaned = [path.strip() for path in paths if path.strip()]
    if not cleaned:
        return ""
    rendered = [f"`{path}`" for path in cleaned]
    if len(rendered) == 1:
        return rendered[0]
    if len(rendered) == 2:
        return f"{rendered[0]} and {rendered[1]}"
    return f"{', '.join(rendered[:-1])}, and {rendered[-1]}"


def _latest_completion_message_after(
    parsed: ParsedSession | None,
    *,
    timestamp: str,
    redacted: bool,
    context: RedactionContext,
) -> str:
    if parsed is None:
        return ""
    for event in reversed(parsed.notable_events):
        label = event.label.lower()
        if "task_complete" not in label and "item_completed" not in label:
            continue
        if timestamp and not _timestamp_after(event.timestamp, timestamp):
            continue
        payload = _parse_tool_call_json(event.text)
        message = _text_value(payload.get("last_agent_message"))
        if redacted:
            message = redact_text(message, context).text
        if message:
            return _excerpt_text(message, limit=500)
    return ""


def _latest_final_answer_after(
    parsed: ParsedSession | None,
    *,
    timestamp: str,
    redacted: bool,
    context: RedactionContext,
) -> str:
    if parsed is None:
        return ""
    for block in reversed(parsed.conversation_entries):
        if block.kind != "assistant":
            continue
        if timestamp and not _timestamp_after(block.timestamp, timestamp):
            continue
        label = block.label.lower()
        if "final_answer" not in label and label != "assistant":
            continue
        text = block.text
        if redacted:
            text = redact_text(text, context).text
        return _excerpt_text(text, limit=500)
    return ""


def _timestamp_after(candidate: str | None, reference: str) -> bool:
    if not candidate:
        return False
    return candidate > reference


def _validation_summary(recent_actions: list[str], resolution_status: str) -> str:
    validation_actions = [
        action for action in recent_actions if action.startswith("ran ")
    ]
    if validation_actions:
        return "; ".join(validation_actions[:3])
    if resolution_status == "answered":
        return "No validation was needed for the latest answer-only turn."
    return "No recent validation signal was detected."


def _commit_summary(repo_state: dict[str, Any]) -> str:
    branch = _string(repo_state.get("repo_branch")) or "unknown branch"
    head = _string(repo_state.get("repo_head_commit")) or "unknown HEAD"
    return f"HEAD `{head}` on `{branch}`."


def _dirty_state_summary(repo_state: dict[str, Any]) -> str:
    if repo_state.get("repo_clean") is True:
        return "Repo appears clean."
    if repo_state.get("repo_clean") is False:
        return "Repo has uncommitted changes."
    return "Repo state could not be determined."


def _build_current_state(
    *,
    parsed: ParsedSession | None,
    summary: dict[str, Any],
    last_substantive_user_request: str,
    recent_actions: list[str],
    resolved_state: dict[str, str],
) -> dict[str, str]:
    status = "in_progress"
    if parsed and parsed.notable_events:
        latest_event = parsed.notable_events[-1]
        lowered = latest_event.label.lower()
        if _has_unresolved_aborted_turn(parsed):
            status = "blocked"
        elif "task_complete" in lowered or "item_completed" in lowered:
            status = "done"

    contextual_request = _string(resolved_state.get("contextual_user_request"))
    if resolved_state.get("latest_user_request_is_context_dependent") == "yes":
        current_focus = _excerpt_text(contextual_request, limit=180)
    else:
        current_focus = _current_focus_text(
            contextual_request
            or last_substantive_user_request
            or _string(summary.get("preview"))
        )
    last_meaningful_outcome = _current_state_outcome(
        resolved_state=resolved_state,
        summary=summary,
        recent_actions=recent_actions,
    )
    if status == "blocked":
        next_action = "Inspect the latest aborted turn or failing command before continuing."
        blocker = "Latest turn or task ended in an aborted state."
    elif status == "done" and resolved_state.get("request_resolution_status") == "answered":
        next_action = (
            "Continue from Resolved State and use the latest answer as the "
            "starting point for the next concrete change."
        )
        blocker = "none"
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


def _current_state_outcome(
    *,
    resolved_state: dict[str, str],
    summary: dict[str, Any],
    recent_actions: list[str],
) -> str:
    resolution_status = _string(resolved_state.get("request_resolution_status"))
    resolution_summary = _string(resolved_state.get("resolution_summary"))
    if resolution_status in {"answered", "handled_with_changes", "completed"}:
        if resolution_summary:
            return resolution_summary
    if recent_actions:
        return recent_actions[0]
    return resolution_summary or _string(summary.get("last_assistant_message"))


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
    resolved_state: dict[str, str],
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
    request_answered = resolved_state.get("request_resolution_status") in {
        "answered",
        "handled_with_changes",
        "completed",
    }
    open_question = (
        last_substantive_user_request
        if last_substantive_user_request.rstrip().endswith("?") and not request_answered
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


def _summary_substantive_user_request(summary: dict[str, Any]) -> str:
    for candidate in (
        _string(summary.get("last_user_message")),
        _string(summary.get("first_user_message")),
        _string(summary.get("preview")),
    ):
        cleaned = _clean_user_request(candidate)
        if cleaned and not _is_trivial_request(cleaned):
            return cleaned
    return ""


def _clean_user_request(message: str) -> str:
    text = message.strip()
    marker_match = re.search(r"#{0,6}\s*My request for Codex:\s*", text)
    if marker_match:
        text = text[marker_match.end() :].strip()
    else:
        filtered_lines: list[str] = []
        skip_open_tabs = False
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            lowered = line.lower()
            if lowered.startswith("# context from my ide setup"):
                continue
            if lowered.startswith("## active file:"):
                continue
            if lowered.startswith("## open tabs:"):
                skip_open_tabs = True
                continue
            if skip_open_tabs:
                if line.startswith("-"):
                    continue
                if line.startswith("#"):
                    skip_open_tabs = False
                else:
                    continue
            filtered_lines.append(raw_line)
        text = "\n".join(filtered_lines).strip()
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

    for block in reversed(conversation_entries[-RECENT_ACTION_LOOKBACK:]):
        action = _normalized_action(block, redacted=redacted, context=context)
        if not action or action in seen:
            continue
        seen.add(action)
        actions.append(action)
        if len(actions) >= 6:
            break

    return actions


def _compaction_summaries(
    notable_events: list[RenderBlock],
    *,
    redacted: bool,
    context: RedactionContext,
) -> list[dict[str, str]]:
    summaries: list[dict[str, str]] = []
    for block in notable_events:
        if "context_compacted" not in block.label:
            continue
        payload = _parse_tool_call_json(block.text)
        summary = _first_text_value(
            payload,
            (
                "summary",
                "context_summary",
                "compacted_summary",
                "message",
                "text",
            ),
        )
        prompt = _first_text_value(
            payload,
            (
                "prompt",
                "compaction_prompt",
                "instructions",
                "system_prompt",
            ),
        )
        if redacted:
            summary = redact_text(summary, context).text
            prompt = redact_text(prompt, context).text
        summary = _excerpt_text(summary, limit=700)
        prompt = _excerpt_text(prompt, limit=700)
        if not summary and not prompt:
            continue
        summaries.append(
            {
                "timestamp": block.timestamp or "",
                "source": "context_compacted",
                "summary": summary,
                "prompt": prompt,
            }
        )
    return summaries[-5:]


def _first_text_value(payload: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        text = _text_value(payload.get(key))
        if text:
            return text
    return ""


def _text_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return " ".join(value.strip().split())
    if isinstance(value, list):
        parts = [_text_value(item) for item in value]
        return " ".join(part for part in parts if part)
    if isinstance(value, dict):
        for key in ("text", "summary", "message", "content"):
            text = _text_value(value.get(key))
            if text:
                return text
        return ""
    return " ".join(str(value).strip().split())


def _linked_child_sessions(
    *,
    metadata: dict[str, Any],
    out_dir: Path,
    redacted: bool,
    context: RedactionContext,
) -> list[dict[str, str]]:
    parent_session_id = _string(metadata.get("session_id"))
    codex_home = _infer_codex_home(metadata)
    if not parent_session_id or codex_home is None:
        return []

    state_path = codex_home / "state_5.sqlite"
    if not state_path.is_file():
        return []

    try:
        connection = sqlite3.connect(f"{state_path.resolve().as_uri()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        if not _has_linked_child_schema(connection):
            return []
        rows = connection.execute(
            """
            SELECT
              e.parent_thread_id,
              e.child_thread_id,
              e.status,
              t.rollout_path,
              t.updated_at,
              t.updated_at_ms,
              t.cwd,
              t.title,
              t.first_user_message,
              t.agent_nickname,
              t.agent_role
            FROM thread_spawn_edges e
            LEFT JOIN threads t ON t.id = e.child_thread_id
            WHERE e.parent_thread_id = ?
            ORDER BY COALESCE(t.updated_at_ms, t.updated_at * 1000, 0) DESC,
                     e.child_thread_id ASC
            LIMIT ?
            """,
            (parent_session_id, LINKED_CHILD_SESSION_LIMIT),
        ).fetchall()
    except (OSError, sqlite3.Error):
        return []
    finally:
        try:
            connection.close()
        except UnboundLocalError:
            pass

    return [
        _linked_child_payload(
            row,
            out_dir=out_dir,
            redacted=redacted,
            context=context,
        )
        for row in rows
    ]


def _has_linked_child_schema(connection: sqlite3.Connection) -> bool:
    edge_columns = _sqlite_table_columns(connection, "thread_spawn_edges")
    thread_columns = _sqlite_table_columns(connection, "threads")
    return {
        "parent_thread_id",
        "child_thread_id",
        "status",
    }.issubset(edge_columns) and {
        "id",
        "rollout_path",
        "updated_at",
        "updated_at_ms",
        "cwd",
        "title",
        "first_user_message",
        "agent_nickname",
        "agent_role",
    }.issubset(thread_columns)


def _sqlite_table_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    try:
        rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    except sqlite3.Error:
        return set()
    return {str(row[1]) for row in rows}


def _linked_child_payload(
    row: sqlite3.Row,
    *,
    out_dir: Path,
    redacted: bool,
    context: RedactionContext,
) -> dict[str, str]:
    child_session_id = _string(row["child_thread_id"])
    child_metadata = _load_child_mirror_metadata(out_dir, child_session_id)
    child_summary = _as_dict(child_metadata.get("summary"))
    layout = mirror_layout(out_dir)
    markdown_relpath = _string(child_metadata.get("markdown_relpath"))
    handoff_relpath = ""
    if (layout.out_dir / layout.handoff_markdown_relpath(child_session_id)).is_file():
        handoff_relpath = layout.handoff_markdown_relpath(child_session_id)

    first_user_message = _string(row["first_user_message"]) or _string(
        child_summary.get("first_user_message")
    )
    latest_assistant_message = _string(child_summary.get("last_assistant_message"))

    return {
        "parent_session_id": _clean_child_text(row["parent_thread_id"], redacted, context, 120),
        "child_session_id": child_session_id,
        "status": _clean_child_text(row["status"], redacted, context, 80),
        "title": _clean_child_text(
            _string(row["title"]) or _string(child_metadata.get("title")),
            redacted,
            context,
            140,
        ),
        "cwd": _clean_child_text(row["cwd"], redacted, context, 220),
        "rollout_path": _clean_child_text(row["rollout_path"], redacted, context, 260),
        "first_user_message": _clean_child_text(first_user_message, redacted, context, 260),
        "latest_assistant_message": _clean_child_text(
            latest_assistant_message,
            redacted,
            context,
            260,
        ),
        "updated_at": _epoch_timestamp_to_iso(row["updated_at_ms"] or row["updated_at"]),
        "agent_nickname": _clean_child_text(row["agent_nickname"], redacted, context, 80),
        "agent_role": _clean_child_text(row["agent_role"], redacted, context, 80),
        "markdown_relpath": markdown_relpath,
        "handoff_markdown_relpath": handoff_relpath,
    }


def _load_child_mirror_metadata(out_dir: Path, child_session_id: str) -> dict[str, Any]:
    if not child_session_id:
        return {}
    metadata_path = mirror_layout(out_dir).metadata_path(child_session_id)
    if not metadata_path.is_file():
        return {}
    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _clean_child_text(
    value: Any,
    redacted: bool,
    context: RedactionContext,
    limit: int,
) -> str:
    text = _text_value(value)
    if redacted:
        text = redact_text(text, context).text
    return _excerpt_text(text, limit=limit)


def _epoch_timestamp_to_iso(value: Any) -> str:
    if value in (None, ""):
        return ""
    try:
        timestamp = int(value)
    except (TypeError, ValueError):
        return _string(value)
    if timestamp > 10_000_000_000:
        timestamp = timestamp // 1000
    try:
        return datetime.fromtimestamp(timestamp, tz=UTC).replace(microsecond=0).isoformat().replace(
            "+00:00",
            "Z",
        )
    except (OSError, OverflowError, ValueError):
        return ""


def _infer_codex_home(metadata: dict[str, Any]) -> Path | None:
    source_file_value = metadata.get("source_file")
    source_relpath_value = metadata.get("source_relpath")
    if not isinstance(source_file_value, str) or not source_file_value.strip():
        return None
    if not isinstance(source_relpath_value, str) or not source_relpath_value.strip():
        return None

    source_file = Path(source_file_value).expanduser().resolve(strict=False)
    source_dir = _infer_source_dir(source_file, source_relpath_value)
    if source_dir.name in {"sessions", "archived_sessions"}:
        return source_dir.parent
    return source_dir


def _child_agent_label(child: dict[str, Any]) -> str:
    nickname = _string(child.get("agent_nickname"))
    role = _string(child.get("agent_role"))
    if nickname and role:
        return f"{nickname} (`{role}`)"
    if nickname:
        return nickname
    if role:
        return f"`{role}`"
    return ""


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

    if _has_unresolved_aborted_turn(parsed):
        return ("Latest turn ended in an aborted state.", "none")

    return ("none", "")


def _has_unresolved_aborted_turn(parsed: ParsedSession) -> bool:
    aborted_timestamp = ""
    for event in reversed(parsed.notable_events):
        if "turn_aborted" in event.label.lower():
            aborted_timestamp = event.timestamp or ""
            break

    if not aborted_timestamp:
        return False

    for event in parsed.notable_events:
        if (event.timestamp or "") <= aborted_timestamp:
            continue
        lowered = event.label.lower()
        if "task_complete" in lowered or "item_completed" in lowered:
            return False

    for block in parsed.conversation_entries:
        if (block.timestamp or "") <= aborted_timestamp:
            continue
        if block.kind in {"assistant", "tool_call", "tool_output"}:
            return False

    return True


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
            files.append(normalized)
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
        "repo_dirty_paths": [],
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
            "repo_dirty_paths": _parse_git_status_paths(status),
        }
    )
    return result


def _parse_git_status_paths(status: str) -> list[dict[str, str]]:
    paths: list[dict[str, str]] = []
    for raw_line in status.splitlines():
        if not raw_line:
            continue
        status_code = raw_line[:2].strip() or "dirty"
        path_text = raw_line[2:].strip() if len(raw_line) > 2 else ""
        if " -> " in path_text:
            path_text = path_text.split(" -> ", 1)[1].strip()
        normalized = _normalize_artifact_path(path_text)
        if not normalized:
            continue
        paths.append({"path": normalized, "status": status_code})
    return paths


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
