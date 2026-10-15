"""Copy-ready restart prompt assembly."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .state import _restart_prompt_child_lines
from .utils import _as_dict, _as_list, _excerpt_text, _string


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
    repo_evidence: dict[str, Any],
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
    repo_evidence_lines = _restart_prompt_repo_evidence_lines(repo_evidence)
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
        *repo_evidence_lines,
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


def _restart_prompt_repo_evidence_lines(repo_evidence: dict[str, Any]) -> list[str]:
    if not repo_evidence.get("include_in_restart_prompt"):
        return []
    sources = [
        _as_dict(source)
        for source in _as_list(repo_evidence.get("sources"))
        if _as_dict(source).get("include_in_restart_prompt")
    ]
    if not sources:
        return []

    lines = [
        "Repo evidence:",
        "- Scope: high-confidence repo evidence only; review before acting.",
        "- Used for synthesis: no",
        f"- Inclusion reason: {repo_evidence.get('inclusion_reason') or 'unknown'}",
        "- Sources:",
    ]
    for source in sources[:5]:
        path = _string(source.get("path")) or "unknown"
        kind = _string(source.get("kind")) or "unknown"
        confidence = source.get("confidence")
        excerpt = _string(source.get("excerpt"))
        suffix = f" - {excerpt}" if excerpt else ""
        lines.append(f"  - {path} ({kind}, confidence {confidence}){suffix}")
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
