"""Handoff generation entry points and transcript snapshots."""

from __future__ import annotations

import json
import re
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..discovery import mirror_layout
from ..html_reader import render_session_reader
from ..index import MirrorEntry, entry_path
from ..markdown import render_session_markdown
from ..parsing import ParsedSession, RenderBlock
from ..redaction import RedactionContext, redact_text
from ..summaries import build_summary
from .artifacts import _build_changed_artifacts
from .children import _linked_child_sessions
from .constants import HandoffResult, HandoffUserTurn
from .evidence import _build_repo_evidence, _build_roadmap_evidence
from .freshness import (
    _best_parsed_timestamp,
    _build_continuity_freshness,
    _max_iso_timestamp,
    _parse_iso_timestamp,
)
from .memory import _build_decisions_and_invariants, _strip_memory_ide_wrapper
from .render import render_handoff_markdown
from .repo import _detect_repo_state, _infer_repo_cwd_from_session_paths
from .restart_prompt import _build_restart_prompt
from .source import _build_source_availability, _load_source_session
from .state import (
    _build_continuation_brief,
    _build_continuity_entry,
    _build_current_state,
    _build_open_loops,
    _build_reentry_posture,
    _build_resolved_state,
    _compaction_summaries,
    _latest_substantive_user_signal,
    _next_best_action_for_brief,
    _recent_actions,
)
from .utils import _as_dict, _excerpt_text, _iso_now, _render_block_payload, _string


def generate_handoff(
    entry: MirrorEntry,
    out_dir: Path | None = None,
    *,
    as_of: str | None = None,
    before_last_user: bool = False,
    before_user: int | None = None,
) -> HandoffResult:
    """Write an extractive handoff bundle for one derived mirror entry."""

    layout = mirror_layout(out_dir)
    layout.handoffs_dir.mkdir(parents=True, exist_ok=True)

    if (
        sum(
            1 for active in (as_of is not None, before_last_user, before_user is not None) if active
        )
        > 1
    ):
        raise ValueError("Use only one historical snapshot mode.")

    session_id = str(entry["session_id"])
    metadata_path = entry_path(entry, "metadata", layout.out_dir)
    markdown_path = entry_path(entry, "markdown", layout.out_dir)
    reader_relpath = str(entry.get("reader_relpath") or layout.reader_relpath(session_id))

    metadata_text = metadata_path.read_text(encoding="utf-8")
    metadata = json.loads(metadata_text)
    transcript_text = markdown_path.read_text(encoding="utf-8")
    reader_metadata_text = metadata_text
    cwd = _string(metadata.get("cwd"))

    parsed = _load_source_session(metadata)
    handoff_artifact_id = session_id
    if as_of or before_last_user or before_user is not None:
        if parsed is None:
            raise ValueError("Historical handoff snapshots require the local source session.")
        parsed, metadata, transcript_text, snapshot_label = _apply_handoff_snapshot(
            parsed=parsed,
            metadata=metadata,
            transcript_text=transcript_text,
            as_of=as_of,
            before_last_user=before_last_user,
            before_user=before_user,
        )
        handoff_artifact_id = f"{session_id}.{snapshot_label}"
        reader_relpath = str(layout.reader_relpath(handoff_artifact_id))
        reader_metadata_text = json.dumps(metadata, indent=2, ensure_ascii=False) + "\n"

    handoff = _build_handoff_payload(
        metadata=metadata,
        transcript_text=transcript_text,
        parsed=parsed,
        reader_relpath=reader_relpath,
        out_dir=layout.out_dir,
        cwd=Path(cwd).expanduser() if cwd else None,
        handoff_artifact_id=handoff_artifact_id,
    )

    handoff_json_path = layout.handoff_json_path(handoff_artifact_id)
    handoff_markdown_path = layout.handoff_markdown_path(handoff_artifact_id)
    handoff_json_path.write_text(
        json.dumps(handoff, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    handoff_markdown_path.write_text(
        render_handoff_markdown(handoff),
        encoding="utf-8",
    )
    reader_path = layout.reader_path(handoff_artifact_id)
    reader_path.parent.mkdir(parents=True, exist_ok=True)
    reader_path.write_text(
        render_session_reader(
            entry=metadata,
            metadata_text=reader_metadata_text,
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


def list_handoff_user_turns(
    entry: MirrorEntry,
    out_dir: Path | None = None,
) -> list[HandoffUserTurn]:
    """List user-message boundaries available for historical handoff snapshots."""

    layout = mirror_layout(out_dir)
    metadata_path = entry_path(entry, "metadata", layout.out_dir)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    parsed = _load_source_session(metadata)
    if parsed is None:
        raise ValueError("Listing handoff turns requires the local source session.")

    turns: list[HandoffUserTurn] = []
    for index, block in enumerate(
        (block for block in parsed.conversation_entries if block.kind == "user"),
        start=1,
    ):
        preview = _excerpt_text(
            " ".join(_strip_memory_ide_wrapper(block.text).split()),
            limit=180,
        )
        turns.append(
            HandoffUserTurn(
                index=index,
                timestamp=_string(block.timestamp) or "n/a",
                preview=preview,
            )
        )
    return turns


def _apply_handoff_snapshot(
    *,
    parsed: ParsedSession,
    metadata: dict[str, Any],
    transcript_text: str,
    as_of: str | None,
    before_last_user: bool,
    before_user: int | None,
) -> tuple[ParsedSession, dict[str, Any], str, str]:
    if before_user is not None:
        truncated = _truncate_parsed_session_before_user(parsed, before_user)
        snapshot_as_of = _best_parsed_timestamp(truncated)
        snapshot_label = f"before-user-{before_user}"
        snapshot_mode = "before_user"
    elif before_last_user:
        truncated = _truncate_parsed_session_before_last_user(parsed)
        snapshot_as_of = _best_parsed_timestamp(truncated)
        snapshot_label = "before-last-user"
        snapshot_mode = "before_last_user"
    else:
        cutoff = _parse_iso_timestamp(as_of or "")
        if cutoff is None:
            raise ValueError(f"Invalid --as-of timestamp: {as_of}")
        truncated = _truncate_parsed_session_as_of(parsed, cutoff)
        snapshot_as_of = _format_iso_timestamp(cutoff)
        snapshot_label = f"asof-{_snapshot_timestamp_slug(snapshot_as_of)}"
        snapshot_mode = "as_of"

    if not truncated.conversation_entries:
        raise ValueError("Historical handoff snapshot has no conversation before the boundary.")

    snapshot_metadata = _snapshot_metadata(
        metadata=metadata,
        parsed=truncated,
        snapshot_mode=snapshot_mode,
        snapshot_as_of=snapshot_as_of,
        snapshot_label=snapshot_label,
    )
    snapshot_transcript = _snapshot_transcript_text(
        metadata=snapshot_metadata,
        parsed=truncated,
        fallback=transcript_text,
    )
    return truncated, snapshot_metadata, snapshot_transcript, snapshot_label


def _truncate_parsed_session_before_last_user(parsed: ParsedSession) -> ParsedSession:
    user_positions = _user_turn_positions(parsed)
    if len(user_positions) < 2:
        raise ValueError("Cannot create --before-last-user snapshot without prior conversation.")
    return _truncate_parsed_session_before_conversation_index(parsed, user_positions[-1])


def _truncate_parsed_session_before_user(
    parsed: ParsedSession,
    user_index: int,
) -> ParsedSession:
    if user_index < 1:
        raise ValueError("--before-user expects a positive 1-based user turn index.")
    user_positions = _user_turn_positions(parsed)
    if user_index > len(user_positions):
        raise ValueError(
            f"--before-user {user_index} is out of range; this session has "
            f"{len(user_positions)} user turn(s)."
        )
    conversation_index = user_positions[user_index - 1]
    if conversation_index <= 0:
        raise ValueError("Cannot create a snapshot before the first user message.")
    return _truncate_parsed_session_before_conversation_index(parsed, conversation_index)


def _user_turn_positions(parsed: ParsedSession) -> list[int]:
    return [
        index for index, block in enumerate(parsed.conversation_entries) if block.kind == "user"
    ]


def _truncate_parsed_session_before_conversation_index(
    parsed: ParsedSession,
    conversation_index: int,
) -> ParsedSession:
    conversation = parsed.conversation_entries[:conversation_index]
    cutoff = _max_iso_timestamp(
        [_string(block.timestamp) for block in conversation]
        + [_string(block.timestamp) for block in parsed.context_entries]
    )
    notable_events = _blocks_at_or_before(parsed.notable_events, cutoff)
    return _replace_parsed_blocks(
        parsed,
        context_entries=parsed.context_entries,
        conversation_entries=conversation,
        notable_events=notable_events,
    )


def _truncate_parsed_session_as_of(
    parsed: ParsedSession,
    cutoff: datetime,
) -> ParsedSession:
    cutoff_text = _format_iso_timestamp(cutoff)
    return _replace_parsed_blocks(
        parsed,
        context_entries=_blocks_at_or_before(parsed.context_entries, cutoff_text),
        conversation_entries=_blocks_at_or_before(parsed.conversation_entries, cutoff_text),
        notable_events=_blocks_at_or_before(parsed.notable_events, cutoff_text),
    )


def _blocks_at_or_before(blocks: list[RenderBlock], cutoff: str) -> list[RenderBlock]:
    if not cutoff:
        return list(blocks)
    cutoff_dt = _parse_iso_timestamp(cutoff)
    if cutoff_dt is None:
        return list(blocks)

    kept: list[RenderBlock] = []
    for block in blocks:
        if not block.timestamp:
            kept.append(block)
            continue
        block_dt = _parse_iso_timestamp(block.timestamp)
        if block_dt is None or block_dt <= cutoff_dt:
            kept.append(block)
    return kept


def _replace_parsed_blocks(
    parsed: ParsedSession,
    *,
    context_entries: list[RenderBlock],
    conversation_entries: list[RenderBlock],
    notable_events: list[RenderBlock],
) -> ParsedSession:
    user_messages = [block.text for block in conversation_entries if block.kind == "user"]
    assistant_messages = [block.text for block in conversation_entries if block.kind == "assistant"]
    return replace(
        parsed,
        context_entries=list(context_entries),
        conversation_entries=list(conversation_entries),
        notable_events=list(notable_events),
        user_messages=user_messages,
        assistant_messages=assistant_messages,
        event_count=len(context_entries) + len(conversation_entries) + len(notable_events),
        context_entry_count=len(context_entries),
        user_message_count=len(user_messages),
        assistant_message_count=len(assistant_messages),
        tool_call_count=sum(1 for item in conversation_entries if item.kind == "tool_call"),
        tool_output_count=sum(1 for item in conversation_entries if item.kind == "tool_output"),
        notable_event_count=len(notable_events),
    )


def _snapshot_metadata(
    *,
    metadata: dict[str, Any],
    parsed: ParsedSession,
    snapshot_mode: str,
    snapshot_as_of: str,
    snapshot_label: str,
) -> dict[str, Any]:
    updated_at = _best_parsed_timestamp(parsed) or snapshot_as_of
    snapshot = dict(metadata)
    snapshot.update(
        {
            "updated_at": updated_at,
            "summary": build_summary(parsed),
            "event_count": parsed.event_count,
            "context_entry_count": parsed.context_entry_count,
            "user_message_count": parsed.user_message_count,
            "assistant_message_count": parsed.assistant_message_count,
            "tool_call_count": parsed.tool_call_count,
            "tool_output_count": parsed.tool_output_count,
            "notable_event_count": parsed.notable_event_count,
            "snapshot_mode": snapshot_mode,
            "snapshot_as_of": snapshot_as_of,
            "snapshot_label": snapshot_label,
            "snapshot_source_session_id": _string(metadata.get("session_id")),
        }
    )
    return snapshot


def _snapshot_transcript_text(
    *,
    metadata: dict[str, Any],
    parsed: ParsedSession,
    fallback: str,
) -> str:
    summary = _as_dict(metadata.get("summary"))
    includes = _as_dict(metadata.get("markdown_includes"))
    try:
        transcript = render_session_markdown(
            parsed=parsed,
            title=_string(metadata.get("title")) or _string(metadata.get("session_id")),
            thread_name=_string(metadata.get("thread_name")),
            updated_at=_string(metadata.get("updated_at")),
            export_profile=_string(metadata.get("export_profile")) or "full",
            summary=summary,
            include_context=includes.get("context") is not False,
            include_tools=includes.get("tools") is not False,
            include_events=includes.get("events") is not False,
        )
    except (TypeError, ValueError):
        return fallback
    if metadata.get("redacted"):
        return redact_text(transcript, RedactionContext.detect()).text
    return transcript


def _snapshot_timestamp_slug(timestamp: str) -> str:
    parsed = _parse_iso_timestamp(timestamp)
    if parsed is None:
        return re.sub(r"[^0-9A-Za-z]+", "-", timestamp).strip("-")[:40] or "unknown"
    return parsed.strftime("%Y%m%dT%H%M%SZ")


def _format_iso_timestamp(timestamp: datetime) -> str:
    return timestamp.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _build_handoff_payload(
    *,
    metadata: dict[str, Any],
    transcript_text: str,
    parsed: ParsedSession | None,
    reader_relpath: str,
    out_dir: Path,
    cwd: Path | None,
    handoff_artifact_id: str | None = None,
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
    if not _string(repo_state.get("repo_root")):
        inferred_cwd = _infer_repo_cwd_from_session_paths(parsed=parsed, summary=summary)
        if inferred_cwd is not None:
            repo_state = _detect_repo_state(inferred_cwd)
            if _string(repo_state.get("repo_root")):
                repo_state["repo_root_source"] = "inferred_from_artifact_paths"
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
    artifact_id = handoff_artifact_id or session_id
    handoff_markdown_relpath = str(layout.handoff_markdown_relpath(artifact_id))
    handoff_json_relpath = str(layout.handoff_json_relpath(artifact_id))
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
    continuity_freshness = _build_continuity_freshness(
        metadata=metadata,
        parsed=parsed,
        repo_state=repo_state,
        out_dir=out_dir,
        linked_child_sessions=linked_child_sessions,
    )
    changed_artifacts = _build_changed_artifacts(
        parsed=parsed,
        resolved_state=resolved_state,
        recent_window=recent_window,
        repo_state=repo_state,
        redacted=redacted,
        context=redaction_context,
    )
    roadmap_evidence = _build_roadmap_evidence(
        parsed=parsed,
        resolved_state=resolved_state,
        current_state=current_state,
        continuation_brief=continuation_brief,
        changed_artifacts=changed_artifacts,
        continuity_freshness=continuity_freshness,
        repo_state=repo_state,
        redacted=redacted,
        context=redaction_context,
    )
    repo_evidence = _build_repo_evidence(
        repo_state=repo_state,
        roadmap_evidence=roadmap_evidence,
        continuity_freshness=continuity_freshness,
        open_loops=open_loops,
        resolved_state=resolved_state,
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
        "repo_head_commit_date": repo_state["repo_head_commit_date"],
        "repo_root_source": repo_state["repo_root_source"],
        "repo_clean": repo_state["repo_clean"],
        "repo_dirty_paths": repo_state["repo_dirty_paths"],
        "snapshot_mode": metadata.get("snapshot_mode", "none"),
        "snapshot_as_of": metadata.get("snapshot_as_of", ""),
        "snapshot_label": metadata.get("snapshot_label", ""),
        "snapshot_source_session_id": metadata.get("snapshot_source_session_id", ""),
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
        continuity_freshness=continuity_freshness,
        roadmap_evidence=roadmap_evidence,
        repo_evidence=repo_evidence,
        changed_artifacts=changed_artifacts,
        decisions_and_invariants=decisions_and_invariants,
        linked_child_sessions=linked_child_sessions,
    )

    provider_id = _string(metadata.get("provider")) or "codex"
    source_availability = _build_source_availability(
        provider_id=provider_id,
        parsed=parsed,
        metadata=metadata,
    )

    return {
        "handoff_schema_version": 1,
        "provider": provider_id,
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
        "continuity_freshness": continuity_freshness,
        "roadmap_evidence": roadmap_evidence,
        "repo_evidence": repo_evidence,
        "changed_artifacts": changed_artifacts,
        "decisions_and_invariants": decisions_and_invariants,
        "reentry_posture": reentry_posture,
        "restart_prompt": restart_prompt,
        "continuity_entry": continuity_entry,
        "open_loops": open_loops,
        "artifacts": artifacts,
        "source_availability": source_availability,
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
