"""Resolved state, current state, re-entry posture, open loops and next actions."""

from __future__ import annotations

import re
from typing import Any

from ..parsing import ParsedSession, RenderBlock
from ..redaction import RedactionContext, redact_text
from .artifacts import _is_recommended_artifact_path
from .constants import RECENT_ACTION_LOOKBACK
from .repo import _has_unresolved_aborted_turn, _latest_failure_signal, _normalized_action
from .utils import (
    _as_dict,
    _as_list,
    _excerpt_text,
    _parse_tool_call_json,
    _string,
    _timestamp_after,
)


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
