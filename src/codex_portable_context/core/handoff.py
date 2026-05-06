"""Extractive handoff bundle helpers for derived mirrors."""

from __future__ import annotations

import json
import re
import sqlite3
import subprocess
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any

from codex_portable_context.providers import get_provider_adapter

from .discovery import mirror_layout
from .html_reader import render_session_reader
from .index import MirrorEntry, entry_path, load_index
from .markdown import pretty_timestamp, render_session_markdown
from .parsing import ParsedSession, RenderBlock
from .redaction import RedactionContext, redact_text
from .summaries import build_summary

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


def render_handoff_markdown(handoff: dict[str, Any]) -> str:
    """Render a readable handoff Markdown document."""

    session = _as_dict(handoff.get("session"))
    artifacts = _as_dict(handoff.get("artifacts"))
    continuation_brief = _as_dict(handoff.get("continuation_brief"))
    resolved_state = _as_dict(handoff.get("resolved_state"))
    restart_prompt = _as_dict(handoff.get("restart_prompt"))
    reentry_posture = _as_dict(handoff.get("reentry_posture"))
    continuity_entry = _as_dict(handoff.get("continuity_entry"))
    continuity_freshness = _as_dict(handoff.get("continuity_freshness"))
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
    roadmap_evidence = _as_dict(handoff.get("roadmap_evidence"))
    changed_artifacts = _as_dict(handoff.get("changed_artifacts"))
    decisions_and_invariants = _as_dict(handoff.get("decisions_and_invariants"))
    transcript_link = _handoff_relpath(_string(artifacts.get("markdown_relpath")))
    metadata_link = _handoff_relpath(_string(artifacts.get("metadata_relpath")))
    reader_link = _handoff_relpath(_string(artifacts.get("reader_relpath")))
    handoff_json_link = _handoff_sibling_relpath(_string(artifacts.get("handoff_json_relpath")))
    primary_label = _string(continuity_entry.get("primary_artifact_relpath")) or _string(
        artifacts.get("handoff_markdown_relpath")
    )
    transcript_fallback_label = _string(
        continuity_entry.get("transcript_fallback_relpath")
    ) or _string(artifacts.get("markdown_relpath"))
    reader_fallback_label = _string(continuity_entry.get("reader_fallback_relpath")) or _string(
        artifacts.get("reader_relpath")
    )
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
    snapshot_mode = _string(artifacts.get("snapshot_mode")) or "none"
    snapshot_as_of = _string(artifacts.get("snapshot_as_of"))
    continuation_evidence = [
        f"- {item}" for item in _as_list(continuation_brief.get("evidence"))
    ] or ["- none"]
    resolution_status = resolved_state.get("request_resolution_status") or "unknown"
    remaining_local_paths = resolved_state.get("remaining_local_only_paths") or "n/a"
    contextual_request = resolved_state.get("contextual_user_request") or "n/a"
    inspection_order_lines = [
        f"- `{item}`" for item in _as_list(changed_artifacts.get("recommended_inspection_order"))
    ] or ["- none"]
    roadmap_sources = _as_list(roadmap_evidence.get("sources"))
    roadmap_source_lines = _roadmap_evidence_markdown_lines(roadmap_sources)

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
        f"- Provider: `{source.get('provider') or handoff.get('provider') or 'unknown'}`",
        f"- Source session available locally: `{'yes' if source.get('available') else 'no'}`",
        f"- Source mode: `{source.get('mode') or 'unknown'}`",
        f"- Historical snapshot: `{'yes' if snapshot_mode != 'none' else 'no'}`",
        f"- Snapshot mode: `{snapshot_mode}`",
        f"- Snapshot as-of: `{snapshot_as_of or 'n/a'}`",
        "",
        f"- Started with: {session.get('preview') or 'n/a'}",
        f"- Last substantive user request: {session.get('last_substantive_user_request') or 'n/a'}",
        f"- Latest assistant reply: {session.get('last_assistant_message') or 'n/a'}",
        f"- Activity: {session.get('activity') or 'n/a'}",
        f"- Environment: {session.get('environment') or 'n/a'}",
        "",
        "## Continuity Freshness",
        "",
        f"- Status: `{continuity_freshness.get('status') or 'unknown'}`",
        f"- Warning: {continuity_freshness.get('warning') or 'none'}",
        f"- Session updated at: `{continuity_freshness.get('session_updated_at') or 'n/a'}`",
        f"- Repo HEAD commit date: `{continuity_freshness.get('repo_head_commit_date') or 'n/a'}`",
        (
            "- Latest same-cwd session: "
            f"`{continuity_freshness.get('latest_same_cwd_session_id') or 'none'}`"
        ),
        f"- Recommendation: {continuity_freshness.get('recommendation') or 'n/a'}",
        "",
        "## Roadmap Evidence",
        "",
        f"- Status: `{roadmap_evidence.get('status') or 'unknown'}`",
        f"- Summary: {roadmap_evidence.get('summary') or 'n/a'}",
        f"- Activation reason: `{roadmap_evidence.get('activation_reason') or 'none'}`",
        (
            "- Included in restart prompt: "
            f"`{'yes' if roadmap_evidence.get('include_in_restart_prompt') else 'no'}`"
        ),
        (
            "- Used for synthesis: "
            f"`{'yes' if roadmap_evidence.get('used_for_synthesis') else 'no'}`"
        ),
        "",
        "### Sources",
        "",
        *roadmap_source_lines,
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
        *[f"- {item}" for item in _as_list(reentry_posture.get("first_turn_contract"))],
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
        f"- Repo root source: `{artifacts.get('repo_root_source') or 'unknown'}`",
        f"- Branch: `{artifacts.get('repo_branch') or 'n/a'}`",
        f"- HEAD commit: `{artifacts.get('repo_head_commit') or 'n/a'}`",
        f"- HEAD commit date: `{artifacts.get('repo_head_commit_date') or 'n/a'}`",
        f"- Repo state: `{repo_state}`",
        f"- Snapshot mode: `{snapshot_mode}`",
        f"- Snapshot as-of: `{snapshot_as_of or 'n/a'}`",
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
                    f"- Timestamp: `{pretty_timestamp(_string(block.get('timestamp')))}`",
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
                    f"- Timestamp: `{pretty_timestamp(_string(tool.get('timestamp')))}`",
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
    try:
        adapter = get_provider_adapter(provider_id)
    except ValueError:
        return None
    return adapter.parse_session_file(source_file.resolve(), source_dir)


def _infer_source_dir(source_file: Path, source_relpath: str) -> Path:
    current = source_file
    for _ in PurePosixPath(source_relpath).parts:
        current = current.parent
    return current


def _build_source_availability(
    *,
    provider_id: str,
    parsed: ParsedSession | None,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    capabilities = _provider_capabilities_payload(provider_id)
    source_file = _string(metadata.get("source_file"))
    source_relpath = _string(metadata.get("source_relpath"))
    source_available = parsed is not None
    exact_recent_window = source_available
    source_mode = SOURCE_MODE_VALUES[0] if source_available else SOURCE_MODE_VALUES[1]
    limitations = _source_limitations(
        source_available=source_available,
        source_file=source_file,
        source_relpath=source_relpath,
        capabilities=capabilities,
    )
    section_sources = _source_section_sources(
        provider_id=provider_id,
        source_available=source_available,
        capabilities=capabilities,
    )

    return {
        "provider": provider_id,
        "mode": source_mode,
        "available": source_available,
        "exact_recent_window": exact_recent_window,
        "source_file": source_file,
        "source_relpath": source_relpath,
        "capabilities": capabilities,
        "section_source_values": list(SECTION_SOURCE_VALUES),
        "section_sources": section_sources,
        "available_sections": _available_sections_from_sources(section_sources),
        "limitations": limitations,
        "note": _source_availability_note(
            source_available=source_available,
            capabilities=capabilities,
        ),
    }


def _provider_capabilities_payload(provider_id: str) -> dict[str, bool]:
    try:
        capabilities = get_provider_adapter(provider_id).capabilities()
    except ValueError:
        return {key: False for key in PROVIDER_CAPABILITY_KEYS}
    return {key: bool(getattr(capabilities, key)) for key in PROVIDER_CAPABILITY_KEYS}


def _source_limitations(
    *,
    source_available: bool,
    source_file: str,
    source_relpath: str,
    capabilities: dict[str, bool],
) -> list[str]:
    limitations: list[str] = []
    if not source_available:
        if source_file and source_relpath:
            limitations.append("Local raw source file was not available or could not be parsed.")
        else:
            limitations.append("Only derived mirror data was available locally.")
    if not capabilities["supports_tools"]:
        limitations.append("Provider adapter does not expose normalized tool activity.")
    if not capabilities["supports_context_sections"]:
        limitations.append("Provider adapter does not expose normalized context sections.")
    if not capabilities["supports_handoff_source_enrichment"]:
        limitations.append("Provider adapter does not support source-backed handoff enrichment.")
    return limitations


def _source_section_sources(
    *,
    provider_id: str,
    source_available: bool,
    capabilities: dict[str, bool],
) -> dict[str, str]:
    bridge_source = "source_backed" if source_available else "derived_mirror"
    recent_source = "source_backed" if source_available else "unavailable"
    tool_source = (
        "source_backed"
        if source_available and capabilities["supports_tools"]
        else "not_supported"
        if not capabilities["supports_tools"]
        else "unavailable"
    )
    codex_enrichment_source = (
        "provider_enrichment"
        if source_available and provider_id == "codex"
        else "not_supported"
        if source_available
        else "unavailable"
    )
    return {
        "session": bridge_source,
        "continuation_brief": bridge_source,
        "resolved_state": bridge_source,
        "current_state": bridge_source,
        "continuity_freshness": "derived_mirror",
        "roadmap_evidence": "derived_mirror",
        "changed_artifacts": bridge_source,
        "decisions_and_invariants": bridge_source,
        "reentry_posture": "derived_mirror",
        "restart_prompt": "derived_mirror",
        "recent_window": recent_source,
        "recent_notable_events": recent_source,
        "recent_tool_activity": tool_source,
        "compaction_summaries": codex_enrichment_source,
        "linked_child_sessions": codex_enrichment_source,
    }


def _available_sections_from_sources(section_sources: dict[str, str]) -> dict[str, bool]:
    return {
        key: value not in {"unavailable", "not_supported"} for key, value in section_sources.items()
    }


def _source_availability_note(
    *,
    source_available: bool,
    capabilities: dict[str, bool],
) -> str:
    if not source_available:
        return "Only derived mirror data was available locally."
    if capabilities["supports_tools"]:
        return "Recent window and tool activity were extracted from the local source session."
    return (
        "Recent window was extracted from the local source session; "
        "tool activity is unavailable for this provider."
    )


def _build_continuity_freshness(
    *,
    metadata: dict[str, Any],
    parsed: ParsedSession | None,
    repo_state: dict[str, Any],
    out_dir: Path,
    linked_child_sessions: list[dict[str, str]],
) -> dict[str, str]:
    session_updated_at = _handoff_session_updated_at(metadata, parsed)
    repo_head_date = _string(repo_state.get("repo_head_commit_date"))
    newer_sessions = _newer_same_cwd_sessions(
        metadata=metadata,
        out_dir=out_dir,
        session_updated_at=session_updated_at,
        linked_child_sessions=linked_child_sessions,
    )
    repo_advanced = _timestamp_after_with_tolerance(
        repo_head_date,
        session_updated_at,
        tolerance=timedelta(minutes=5),
    )

    latest_same_cwd = newer_sessions[0] if newer_sessions else {}
    latest_same_cwd_id = _string(latest_same_cwd.get("session_id"))
    latest_same_cwd_updated_at = _string(latest_same_cwd.get("updated_at"))

    warnings: list[str] = []
    if latest_same_cwd_id:
        warnings.append(
            "A newer exported session uses the same working directory "
            f"({latest_same_cwd_id} at {latest_same_cwd_updated_at})."
        )
    if repo_advanced:
        warnings.append(
            "The current repo HEAD commit is newer than this session's exported "
            "conversation timestamp."
        )

    if latest_same_cwd_id and repo_advanced:
        status = "stale_newer_same_cwd_and_repo_advanced"
    elif latest_same_cwd_id:
        status = "stale_newer_same_cwd_session"
    elif repo_advanced:
        status = "stale_repo_advanced_after_session"
    elif not session_updated_at:
        status = "unknown"
    else:
        status = "fresh"

    if warnings:
        recommendation = (
            "Treat this handoff as potentially stale. Start in review or plan "
            "mode, inspect the latest same-repo session or committed roadmap, "
            "and do not implement from the old continuation brief until the "
            "user confirms the active line."
        )
    elif status == "unknown":
        recommendation = (
            "Timestamp freshness could not be verified; use the restart prompt's "
            "read-only first turn before acting."
        )
    else:
        recommendation = "No freshness warning detected."

    return {
        "status": status,
        "warning": " ".join(warnings) if warnings else "none",
        "session_updated_at": session_updated_at,
        "repo_head_commit_date": repo_head_date,
        "latest_same_cwd_session_id": latest_same_cwd_id,
        "latest_same_cwd_updated_at": latest_same_cwd_updated_at,
        "recommendation": recommendation,
    }


def _build_roadmap_evidence(
    *,
    parsed: ParsedSession | None,
    resolved_state: dict[str, str],
    current_state: dict[str, str],
    continuation_brief: dict[str, Any],
    changed_artifacts: dict[str, Any],
    continuity_freshness: dict[str, str],
    repo_state: dict[str, Any],
    redacted: bool,
    context: RedactionContext,
) -> dict[str, Any]:
    repo_root = _string(repo_state.get("repo_root"))
    if not repo_root:
        return _empty_roadmap_evidence(
            status="unavailable",
            summary="Repo root was unavailable, so roadmap evidence was not scanned.",
        )

    root = Path(repo_root).expanduser()
    if not root.is_dir():
        return _empty_roadmap_evidence(
            status="unavailable",
            summary="Repo root does not exist locally, so roadmap evidence was not scanned.",
        )

    sources = _roadmap_evidence_sources(root=root, redacted=redacted, context=context)
    if not sources:
        return _empty_roadmap_evidence(
            status="none",
            summary="No conservative roadmap or status documents were discovered.",
        )

    activation_reason = _roadmap_activation_reason(
        parsed=parsed,
        resolved_state=resolved_state,
        current_state=current_state,
        continuation_brief=continuation_brief,
        changed_artifacts=changed_artifacts,
        continuity_freshness=continuity_freshness,
    )
    source_paths = [source["path"] for source in sources]
    return {
        "status": "found",
        "summary": (
            f"Found {len(sources)} roadmap/status evidence source(s). "
            "This slice only cites sources; it does not synthesize or override "
            "conversation state."
        ),
        "sources": sources,
        "recommended_inspection_order": source_paths[:6],
        "activation_reason": activation_reason or "none",
        "include_in_restart_prompt": bool(activation_reason),
        "used_for_synthesis": False,
    }


def _empty_roadmap_evidence(*, status: str, summary: str) -> dict[str, Any]:
    return {
        "status": status,
        "summary": summary,
        "sources": [],
        "recommended_inspection_order": [],
        "activation_reason": "none",
        "include_in_restart_prompt": False,
        "used_for_synthesis": False,
    }


def _roadmap_evidence_sources(
    *,
    root: Path,
    redacted: bool,
    context: RedactionContext,
) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for path in _candidate_roadmap_paths(root):
        source = _roadmap_source_from_path(path, root=root)
        if not source:
            continue
        if redacted:
            source = {
                **source,
                "path": redact_text(source["path"], context).text,
                "excerpt": redact_text(source["excerpt"], context).text,
            }
        sources.append(source)
        if len(sources) >= 8:
            break
    return sources


def _candidate_roadmap_paths(root: Path) -> list[Path]:
    candidates: list[Path] = []

    def add(path: Path) -> None:
        if path.is_file() and path not in candidates:
            candidates.append(path)

    for relpath in ROADMAP_KNOWN_RELATIVE_PATHS:
        add(root / relpath)

    for pattern in ROADMAP_GLOB_PATTERNS:
        for path in sorted(root.glob(pattern)):
            add(path)

    return candidates


def _roadmap_source_from_path(path: Path, *, root: Path) -> dict[str, Any]:
    try:
        relpath = path.relative_to(root).as_posix()
    except ValueError:
        relpath = path.as_posix()

    try:
        text = path.read_text(encoding="utf-8", errors="replace")[:120_000]
    except OSError:
        return {}

    signals = _roadmap_signals(text, relpath)
    if not signals:
        return {}

    return {
        "path": relpath,
        "kind": _roadmap_source_kind(relpath),
        "reason": _roadmap_source_reason(relpath),
        "signals": signals[:6],
        "excerpt": _roadmap_source_excerpt(text),
    }


def _roadmap_source_kind(path: str) -> str:
    lowered = path.lower()
    if "next" in lowered and "step" in lowered:
        return "next_steps"
    if "roadmap" in lowered:
        return "roadmap"
    if "strategy" in lowered:
        return "strategy"
    if "decision" in lowered:
        return "decision_record"
    if "status" in lowered:
        return "status"
    return "roadmap_candidate"


def _roadmap_source_reason(path: str) -> str:
    kind = _roadmap_source_kind(path)
    return {
        "next_steps": "known_next_steps_doc",
        "roadmap": "roadmap_doc",
        "strategy": "strategy_doc",
        "decision_record": "decision_doc",
        "status": "status_doc",
    }.get(kind, "roadmap_candidate")


def _roadmap_signals(text: str, path: str) -> list[str]:
    lowered = f"{path}\n{text}".lower()
    signals: list[str] = []
    for marker in ROADMAP_SIGNAL_MARKERS:
        if marker in lowered and marker not in signals:
            signals.append(marker)
    return signals


def _roadmap_source_excerpt(text: str) -> str:
    fallback = ""
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        line = stripped.strip("-* ")
        if not line or line in {"---", "```"}:
            continue
        is_heading = stripped.startswith("#")
        if not fallback and not line.startswith("#"):
            fallback = line
        if is_heading and _is_generic_roadmap_heading(line):
            continue
        lowered = line.lower()
        if any(marker in lowered for marker in ROADMAP_SIGNAL_MARKERS):
            return _excerpt_text(line, limit=220)
    return _excerpt_text(fallback, limit=220) if fallback else ""


def _is_generic_roadmap_heading(line: str) -> bool:
    cleaned = line.strip("# ").strip().lower()
    return cleaned in {
        "next step",
        "next steps",
        "roadmap",
        "status",
        "current state",
    }


def _roadmap_activation_reason(
    *,
    parsed: ParsedSession | None,
    resolved_state: dict[str, str],
    current_state: dict[str, str],
    continuation_brief: dict[str, Any],
    changed_artifacts: dict[str, Any],
    continuity_freshness: dict[str, str],
) -> str:
    freshness_status = _string(continuity_freshness.get("status"))
    if freshness_status.startswith("stale_"):
        return "freshness_warning"

    recommended = " ".join(
        _string(path) for path in _as_list(changed_artifacts.get("recommended_inspection_order"))
    ).lower()
    if "next_steps" in recommended or "roadmap" in recommended:
        return "roadmap_artifact_referenced"

    haystack = " ".join(
        (
            _string(resolved_state.get("latest_user_request")),
            _string(resolved_state.get("contextual_user_request")),
            _string(resolved_state.get("resolution_summary")),
            _string(current_state.get("current_focus")),
            _string(current_state.get("last_meaningful_outcome")),
            _string(continuation_brief.get("what_we_were_doing")),
        )
    ).lower()
    if any(
        marker in haystack
        for marker in (
            "handoff prompt",
            "restart prompt",
            "roadmap",
            "next_steps",
            "feedback",
            "compare this",
            "comparemos",
            "continuation",
            "continuidad",
        )
    ):
        return "recent_meta_or_roadmap_discussion"

    if parsed and parsed.user_message_count >= 50:
        return "long_session"

    return ""


def _handoff_session_updated_at(
    metadata: dict[str, Any],
    parsed: ParsedSession | None,
) -> str:
    candidates = [_string(metadata.get("updated_at")), _string(metadata.get("session_timestamp"))]
    if parsed:
        candidates.append(_best_parsed_timestamp(parsed))
    return _max_iso_timestamp(candidates)


def _best_parsed_timestamp(parsed: ParsedSession) -> str:
    candidates = [_string(parsed.session_timestamp)]
    candidates.extend(_string(block.timestamp) for block in parsed.context_entries)
    candidates.extend(_string(block.timestamp) for block in parsed.conversation_entries)
    candidates.extend(_string(block.timestamp) for block in parsed.notable_events)
    return _max_iso_timestamp(candidates)


def _max_iso_timestamp(candidates: list[str]) -> str:
    best_text = ""
    best_dt: datetime | None = None
    fallback: list[str] = []
    for candidate in candidates:
        text = _string(candidate)
        if not text:
            continue
        parsed = _parse_iso_timestamp(text)
        if parsed is None:
            fallback.append(text)
            continue
        if best_dt is None or parsed > best_dt:
            best_dt = parsed
            best_text = text
    if best_text:
        return best_text
    return max(fallback) if fallback else ""


def _newer_same_cwd_sessions(
    *,
    metadata: dict[str, Any],
    out_dir: Path,
    session_updated_at: str,
    linked_child_sessions: list[dict[str, str]],
) -> list[dict[str, Any]]:
    cwd = _normalize_freshness_path(_string(metadata.get("cwd")))
    session_id = _string(metadata.get("session_id"))
    if not cwd or not session_id or not session_updated_at:
        return []

    child_ids = {
        _string(child.get("child_session_id"))
        for child in linked_child_sessions
        if _string(child.get("child_session_id"))
    }
    try:
        entries = load_index(out_dir)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

    matches: list[dict[str, Any]] = []
    for entry in entries:
        candidate_id = _string(entry.get("session_id"))
        if not candidate_id or candidate_id == session_id or candidate_id in child_ids:
            continue
        if _normalize_freshness_path(_string(entry.get("cwd"))) != cwd:
            continue
        candidate_updated_at = _string(entry.get("updated_at"))
        if not _timestamp_after(candidate_updated_at, session_updated_at):
            continue
        matches.append(
            {
                "session_id": candidate_id,
                "title": _string(entry.get("title")),
                "updated_at": candidate_updated_at,
            }
        )

    return sorted(
        matches,
        key=lambda item: (_string(item.get("updated_at")), _string(item.get("session_id"))),
        reverse=True,
    )[:3]


def _normalize_freshness_path(path: str) -> str:
    if not path:
        return ""
    try:
        return Path(path).expanduser().resolve(strict=False).as_posix()
    except OSError:
        return path.strip().replace("\\", "/").rstrip("/")


def _timestamp_after_with_tolerance(
    candidate: str,
    reference: str,
    *,
    tolerance: timedelta,
) -> bool:
    candidate_dt = _parse_iso_timestamp(candidate)
    reference_dt = _parse_iso_timestamp(reference)
    if candidate_dt is None or reference_dt is None:
        return False
    return candidate_dt - reference_dt > tolerance


def _parse_iso_timestamp(text: str) -> datetime | None:
    value = _string(text)
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


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
    latest_resolved_request = (
        contextual_request
        if resolution_status
        in {
            "answered",
            "handled_with_changes",
            "completed",
            "derived_only",
        }
        else ""
    )

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
        "confidence": "high"
        if source_available
        and resolution_status
        in {
            "answered",
            "handled_with_changes",
        }
        else "medium"
        if source_available
        else "low",
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
        _string(item.get("text")) for item in recent_window if isinstance(item, dict)
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
    text = _strip_embedded_restart_prompt_payload(text)
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
    if re.search(r"\s+[/\\]\s+", cleaned):
        return ""
    if "\n" in cleaned or len(cleaned) > 260:
        return ""
    if re.search(r"\s--?[A-Za-z0-9][\w-]*(?:\s|=)", cleaned):
        return ""
    if "/" not in cleaned and "." not in Path(cleaned).name:
        return ""
    return cleaned


def _strip_embedded_restart_prompt_payload(text: str) -> str:
    marker_index = text.lower().find("continue from a local extractive handoff")
    if marker_index < 0:
        return text
    return text[:marker_index].strip()


def _resolve_artifact_path(path: str, *, repo_root: str) -> str:
    normalized = _normalize_artifact_path(path)
    if not normalized:
        return normalized
    repo_relative = _repo_relative_artifact_path(normalized, repo_root=repo_root)
    if repo_relative:
        return repo_relative
    if _is_extensionless_relative_nonexistent_path(normalized, repo_root=repo_root):
        return ""
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


def _is_extensionless_relative_nonexistent_path(path: str, *, repo_root: str) -> bool:
    if not repo_root:
        return False
    cleaned = path.rstrip("/")
    if not cleaned or Path(cleaned).is_absolute():
        return False
    if "/" not in cleaned and "\\" not in cleaned:
        return False
    if Path(cleaned).suffix:
        return False

    root = Path(repo_root).expanduser()
    if not root.is_dir():
        return False
    return not (root / cleaned).exists()


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
        relative = candidate.resolve(strict=False).relative_to(root.resolve(strict=False))
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


def _roadmap_evidence_markdown_lines(items: list[Any]) -> list[str]:
    if not items:
        return ["- none"]
    lines: list[str] = []
    for item in items[:8]:
        source = _as_dict(item)
        path = _string(source.get("path")) or "unknown"
        reason = _string(source.get("reason")) or "unknown"
        excerpt = _string(source.get("excerpt"))
        signals = ", ".join(_as_list(source.get("signals"))[:4])
        suffix_parts = []
        if signals:
            suffix_parts.append(f"signals: {signals}")
        if excerpt:
            suffix_parts.append(f"excerpt: {excerpt}")
        suffix = f" - {'; '.join(suffix_parts)}" if suffix_parts else ""
        lines.append(f"- `{path}` (`{reason}`){suffix}")
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
            if source == "context_structural_memory" and _is_low_value_structural_memory(candidate):
                continue
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
    if not looks_like_heading and not (stripped.startswith("**") and stripped.endswith("**")):
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
    if not looks_like_heading and not (stripped.startswith("**") and stripped.endswith("**")):
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
    segments = _memory_text_segments(
        _strip_embedded_restart_prompt_payload(_strip_memory_ide_wrapper(text))
    )
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
    if _is_low_value_memory_candidate(cleaned):
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


def _is_low_value_structural_memory(text: str) -> bool:
    lowered = text.lower()
    if lowered.startswith("important boundary: add a minimal test suite that validates:"):
        return True
    low_value_markers = (
        "binary image validation",
        "the image is validated and normalized",
        "input validation for binary brand images",
        "schema behavior",
        "api health endpoint",
        "validates: imports",
        "retrieval contract integrity",
    )
    return any(marker in lowered for marker in low_value_markers)


def _is_low_value_memory_candidate(text: str) -> bool:
    lowered = text.lower().strip()
    if _is_low_value_structural_memory(text):
        return True
    if "continue from a local extractive handoff" in lowered:
        return True
    if "choose `review`, `plan`, or `implement`" in lowered:
        return True
    if "no validation was needed" in lowered:
        return True
    if "any assumptions or blockers discovered" in lowered:
        return True
    low_value_prefixes = (
        "initial operating mode:",
        "do not run commands",
        "do not implement",
        "do not skip any section",
        "before taking action, ask the user",
        "session:",
        "session id:",
        "repo root:",
        "branch:",
        "head:",
        "repo state:",
        "continuity freshness:",
        "re-entry posture:",
        "first response contract:",
        "required first response format:",
        "summarize the recovered context",
        "state the inferred prior-session",
        "list the next steps you would take if confirmed",
        "candidate next steps if confirmed:",
        "confirmation question:",
        "continuation brief:",
        "resolved state:",
        "validation summary:",
        "dirty state summary:",
        "changed / key artifacts:",
        "recommended inspection order:",
        "artifact links:",
        "first action:",
        "pending validation:",
        "veamos la respuesta",
        "veamos este feedback",
        "comparemos",
        "compare this handoff prompt",
        "este sería correcto",
        "este seria correcto",
        "high finding sobre",
    )
    return lowered.startswith(low_value_prefixes)


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
    continuity_freshness: dict[str, str],
    roadmap_evidence: dict[str, Any],
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
    contract_lines = [f"- {item}" for item in _as_list(reentry_posture.get("first_turn_contract"))]
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
    freshness_lines = _restart_prompt_freshness_lines(continuity_freshness)
    session_label = _restart_prompt_session_label(
        session_title=session_title,
        artifacts=artifacts,
        session_id=session_id,
    )
    snapshot_lines = _restart_prompt_snapshot_lines(artifacts)
    roadmap_lines = _restart_prompt_roadmap_lines(roadmap_evidence)
    repo_root_source = _string(artifacts.get("repo_root_source"))
    repo_root_source_lines = (
        [f"Repo root source: {repo_root_source}"]
        if repo_root_source and repo_root_source != "metadata_cwd"
        else []
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
        f"Session: {session_label}",
        f"Session ID: {session_id}",
        f"Repo root: {artifacts.get('repo_root') or 'n/a'}",
        *repo_root_source_lines,
        f"Branch: {artifacts.get('repo_branch') or 'n/a'}",
        f"HEAD: {artifacts.get('repo_head_commit') or 'n/a'}",
        f"Repo state: {repo_state}",
        *snapshot_lines,
        "",
        "Continuity freshness:",
        *freshness_lines,
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
        *roadmap_lines,
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


def _restart_prompt_session_label(
    *,
    session_title: str,
    artifacts: dict[str, Any],
    session_id: str,
) -> str:
    title = session_title.strip()
    repo_root = _string(artifacts.get("repo_root"))
    repo_name = Path(repo_root).name if repo_root else ""
    if title and not _session_title_conflicts_with_repo(title, repo_name):
        return title
    if repo_name:
        return f"{repo_name} continuity handoff"
    return title or session_id


def _session_title_conflicts_with_repo(title: str, repo_name: str) -> bool:
    if not repo_name:
        return False
    title_key = _normalize_repo_name(title)
    repo_key = _normalize_repo_name(repo_name)
    if repo_key and repo_key in title_key:
        return False
    lowered = title.lower()
    if not any(
        marker in lowered
        for marker in (
            "source of truth",
            "repo",
            "repository",
            "project",
            "proyecto",
        )
    ):
        return False
    mentioned_names = re.findall(r"`([^`]+)`", title)
    return any(_normalize_repo_name(name) != repo_key for name in mentioned_names)


def _normalize_repo_name(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def _restart_prompt_snapshot_lines(artifacts: dict[str, Any]) -> list[str]:
    mode = _string(artifacts.get("snapshot_mode")) or "none"
    if mode == "none":
        return []
    as_of = _string(artifacts.get("snapshot_as_of")) or "unknown"
    source_session_id = _string(artifacts.get("snapshot_source_session_id")) or "unknown"
    return [
        "",
        "Historical snapshot:",
        f"- Mode: {mode}",
        f"- As of: {as_of}",
        f"- Source session ID: {source_session_id}",
        (
            "- Scope: this prompt is generated from the session prefix up to "
            "the snapshot boundary, not from the full current thread."
        ),
    ]


def _restart_prompt_roadmap_lines(roadmap_evidence: dict[str, Any]) -> list[str]:
    if not roadmap_evidence.get("include_in_restart_prompt"):
        return []
    sources = _as_list(roadmap_evidence.get("sources"))
    if not sources:
        return []

    lines = [
        "Roadmap evidence:",
        (
            "- Scope: source-attributed repo evidence only; do not override "
            "the transcript without review."
        ),
        "- Used for synthesis: no",
        f"- Activation reason: {roadmap_evidence.get('activation_reason') or 'unknown'}",
        "- Sources:",
    ]
    for source in sources[:4]:
        item = _as_dict(source)
        path = _string(item.get("path")) or "unknown"
        reason = _string(item.get("reason")) or "unknown"
        excerpt = _string(item.get("excerpt"))
        suffix = f" - {excerpt}" if excerpt else ""
        lines.append(f"  - {path} ({reason}){suffix}")
    lines.append("")
    return lines


def _restart_prompt_path_lines(paths: list[Any]) -> list[str]:
    if not paths:
        return ["  - none"]
    return [f"  - {_string(path)}" for path in paths[:8]]


def _restart_prompt_freshness_lines(freshness: dict[str, str]) -> list[str]:
    status = _string(freshness.get("status")) or "unknown"
    warning = _string(freshness.get("warning")) or "none"
    recommendation = _string(freshness.get("recommendation")) or "n/a"
    lines = [
        f"- Status: {status}",
        f"- Warning: {warning}",
        f"- Recommendation: {recommendation}",
    ]
    latest_same_cwd = _string(freshness.get("latest_same_cwd_session_id"))
    if latest_same_cwd:
        updated_at = _string(freshness.get("latest_same_cwd_updated_at")) or "unknown time"
        lines.append(f"- Newer same-cwd session: {latest_same_cwd} at {updated_at}")
    repo_head_date = _string(freshness.get("repo_head_commit_date"))
    if repo_head_date:
        lines.append(f"- Repo HEAD commit date: {repo_head_date}")
    return lines


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
        "architect_reviewer" if _looks_like_review_posture(haystack) else "operator_reviewer"
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
        else ("recover the current unresolved state before choosing review, plan, or implement.")
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
    validation_actions = [action for action in recent_actions if action.startswith("ran ")]
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
            contextual_request or last_substantive_user_request or _string(summary.get("preview"))
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
            "Review the handoff artifacts and decide whether to start a new follow-up task."
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
    validation_ran = any(action == "ran ./scripts/validate-python-v2" for action in recent_actions)
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
        return (
            datetime.fromtimestamp(timestamp, tz=UTC)
            .replace(microsecond=0)
            .isoformat()
            .replace(
                "+00:00",
                "Z",
            )
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


def _infer_repo_cwd_from_session_paths(
    *,
    parsed: ParsedSession | None,
    summary: dict[str, Any],
) -> Path | None:
    candidate_paths = _absolute_session_path_candidates(parsed=parsed, summary=summary)
    if not candidate_paths:
        return None

    repo_counts: dict[str, int] = {}
    for candidate in candidate_paths:
        repo_root = _git_repo_root_for_path(candidate)
        if not repo_root:
            continue
        repo_counts[repo_root] = repo_counts.get(repo_root, 0) + 1

    if not repo_counts:
        return None
    ranked = sorted(repo_counts.items(), key=lambda item: item[1], reverse=True)
    if len(ranked) > 1 and ranked[0][1] <= ranked[1][1]:
        return None
    return Path(ranked[0][0])


def _absolute_session_path_candidates(
    *,
    parsed: ParsedSession | None,
    summary: dict[str, Any],
) -> list[Path]:
    candidates: list[Path] = []

    def append_candidate(raw_path: str) -> None:
        normalized = _normalize_artifact_path(raw_path)
        if not normalized:
            return
        path = Path(normalized).expanduser()
        if path.is_absolute():
            candidates.append(path)

    summary_values = [
        summary.get("preview"),
        summary.get("last_user_message"),
        summary.get("last_assistant_message"),
        summary.get("last_tool_summary"),
    ]
    for value in summary_values:
        for path in _path_mentions_from_text(_string(value)):
            append_candidate(path)

    if parsed is None:
        return candidates

    blocks = [
        *parsed.context_entries[-20:],
        *parsed.conversation_entries[-RECENT_ACTION_LOOKBACK:],
        *parsed.notable_events[-20:],
    ]
    for block in blocks:
        for path in _path_mentions_from_text(block.text):
            append_candidate(path)
        if block.kind != "tool_call":
            continue
        payload = _parse_tool_call_json(block.text)
        append_candidate(_string(payload.get("workdir")))
        append_candidate(_string(payload.get("cwd")))

    return candidates


def _git_repo_root_for_path(path: Path) -> str:
    candidate = path.expanduser()
    search_dir = candidate if candidate.exists() and candidate.is_dir() else candidate.parent
    if not search_dir.exists():
        return ""
    try:
        return subprocess.run(
            ["git", "-C", str(search_dir), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return ""


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
        "repo_head_commit_date": "",
        "repo_root_source": "",
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
        head_commit_date = subprocess.run(
            ["git", "-C", repo_root, "show", "-s", "--format=%cI", "HEAD"],
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
            "repo_head_commit_date": head_commit_date,
            "repo_root_source": "metadata_cwd",
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
