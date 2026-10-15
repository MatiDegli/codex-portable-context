"""Markdown rendering of a handoff bundle."""

from __future__ import annotations

from typing import Any

from ..markdown import pretty_timestamp
from .children import _child_agent_label
from .utils import _as_dict, _as_list, _handoff_relpath, _handoff_sibling_relpath, _string


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
    repo_evidence = _as_dict(handoff.get("repo_evidence"))
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
    repo_sources = _as_list(repo_evidence.get("sources"))
    repo_source_lines = _repo_evidence_markdown_lines(repo_sources)

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
        "## Repo Evidence",
        "",
        f"- Status: `{repo_evidence.get('status') or 'unknown'}`",
        f"- Summary: {repo_evidence.get('summary') or 'n/a'}",
        f"- Max confidence: `{repo_evidence.get('max_confidence') or 0.0}`",
        (
            "- Included in restart prompt: "
            f"`{'yes' if repo_evidence.get('include_in_restart_prompt') else 'no'}`"
        ),
        (f"- Used for synthesis: `{'yes' if repo_evidence.get('used_for_synthesis') else 'no'}`"),
        f"- Inclusion reason: `{repo_evidence.get('inclusion_reason') or 'none'}`",
        "",
        "### Sources",
        "",
        *repo_source_lines,
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


def _repo_evidence_markdown_lines(items: list[Any]) -> list[str]:
    if not items:
        return ["- none"]
    lines: list[str] = []
    for item in items[:10]:
        source = _as_dict(item)
        path = _string(source.get("path")) or "unknown"
        kind = _string(source.get("kind")) or "unknown"
        confidence = source.get("confidence")
        excerpt = _string(source.get("excerpt"))
        prompt_flag = "prompt" if source.get("include_in_restart_prompt") else "evidence"
        suffix = f" - {excerpt}" if excerpt else ""
        lines.append(f"- `{path}` (`{kind}`, `{confidence}`, `{prompt_flag}`){suffix}")
    return lines


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
