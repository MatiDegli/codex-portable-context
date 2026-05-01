"""Quality audit helpers for generated handoff memory sections."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .discovery import mirror_layout
from .handoff import generate_handoff
from .index import MirrorEntry, entry_session_id, entry_title, sort_entries
from .listing import truncate
from .resolve import resolve_unique_entry

MEMORY_KEYS = (
    "decisions",
    "invariants",
    "rejected_paths",
    "open_architecture_questions",
)


@dataclass(frozen=True, slots=True)
class HandoffAuditOptions:
    """Options for selecting and auditing handoff memory quality."""

    limit: int = 10
    selectors: tuple[str, ...] = ()
    generate: bool = True


def audit_handoffs(
    entries: list[MirrorEntry],
    *,
    out_dir: Path,
    options: HandoffAuditOptions,
) -> dict[str, Any]:
    """Audit selected handoffs and return a JSON-serializable report."""

    selected_entries = _selected_entries(entries, options)
    items = [
        _audit_entry(entry, out_dir=out_dir, generate=options.generate)
        for entry in selected_entries
    ]
    return {
        "summary": _audit_summary(items),
        "items": items,
    }


def render_handoff_audit(report: dict[str, Any]) -> str:
    """Render a compact terminal table for a handoff audit report."""

    summary = _as_dict(report.get("summary"))
    lines = [
        (
            "Audited {audited} session(s): {covered} with memory, {empty} empty, "
            "{errored} errored."
        ).format(
            audited=summary.get("audited", 0),
            covered=summary.get("covered", 0),
            empty=summary.get("empty", 0),
            errored=summary.get("errored", 0),
        ),
        (
            "Confidence: high={high}, medium={medium}, low={low}. "
            "Average memory items: {average:.1f}."
        ).format(
            high=summary.get("confidence_counts", {}).get("high", 0),
            medium=summary.get("confidence_counts", {}).get("medium", 0),
            low=summary.get("confidence_counts", {}).get("low", 0),
            average=float(summary.get("average_memory_items", 0.0)),
        ),
        (
            "Readiness: ready={ready}, review={review}, weak={weak}, "
            "minimal={minimal}, error={error}."
        ).format(
            ready=summary.get("readiness_counts", {}).get("ready", 0),
            review=summary.get("readiness_counts", {}).get("review", 0),
            weak=summary.get("readiness_counts", {}).get("weak", 0),
            minimal=summary.get("readiness_counts", {}).get("minimal_expected", 0),
            error=summary.get("readiness_counts", {}).get("error", 0),
        ),
        (
            "Prompt compliance: pass={passed}, review={review}, fail={fail}, "
            "error={error}."
        ).format(
            passed=summary.get("prompt_compliance_counts", {}).get("pass", 0),
            review=summary.get("prompt_compliance_counts", {}).get("review", 0),
            fail=summary.get("prompt_compliance_counts", {}).get("fail", 0),
            error=summary.get("prompt_compliance_counts", {}).get("error", 0),
        ),
        (
            "Purpose: substantive={substantive}, review={review}, active={active}, "
            "bootstrap={bootstrap}, transport={transport}, noise={noise}."
        ).format(
            substantive=summary.get("purpose_counts", {}).get("substantive_work", 0),
            review=summary.get("purpose_counts", {}).get("review_or_audit", 0),
            active=summary.get("purpose_counts", {}).get("active_in_progress", 0),
            bootstrap=summary.get("purpose_counts", {}).get("bootstrap_or_ack", 0),
            transport=summary.get("purpose_counts", {}).get("transport_test", 0),
            noise=summary.get("purpose_counts", {}).get("empty_or_noise", 0),
        ),
        "",
        (
            f"{'SESSION':<8}  {'TITLE':<30}  {'READY':<16}  {'PURPOSE':<14}  "
            f"{'CONF':<6}  {'D':>2} {'I':>2} {'R':>2} {'O':>2}  {'ROLE':<18}  "
            f"{'SOURCES':<28}  FLAGS"
        ),
    ]

    for raw_item in _as_list(report.get("items")):
        item = _as_dict(raw_item)
        counts = _as_dict(item.get("counts"))
        sources = ", ".join(str(source) for source in _as_list(item.get("sources")))
        flags = ", ".join(str(flag) for flag in _as_list(item.get("flags"))) or "-"
        lines.append(
            f"{str(item.get('session_id', ''))[:8]:<8}  "
            f"{truncate(str(item.get('title') or ''), 30):<30}  "
            f"{str(item.get('readiness') or 'error'):<16}  "
            f"{truncate(str(item.get('session_purpose') or 'unknown'), 14):<14}  "
            f"{str(item.get('confidence') or 'error'):<6}  "
            f"{int(counts.get('decisions', 0)):>2} "
            f"{int(counts.get('invariants', 0)):>2} "
            f"{int(counts.get('rejected_paths', 0)):>2} "
            f"{int(counts.get('open_architecture_questions', 0)):>2}  "
            f"{truncate(str(item.get('role_hint') or 'unknown'), 18):<18}  "
            f"{truncate(sources or '-', 28):<28}  "
            f"{flags}"
        )

    return "\n".join(lines) + "\n"


def write_e2e_manifest(report: dict[str, Any], path: Path) -> Path:
    """Write a manual-only restart prompt E2E manifest for selected audit items."""

    manifest = build_e2e_manifest(report)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def build_e2e_manifest(report: dict[str, Any]) -> dict[str, Any]:
    """Build a manual E2E trial manifest without launching agents or threads."""

    items = [_as_dict(item) for item in _as_list(report.get("items"))]
    return {
        "kind": "restart_prompt_e2e_manifest",
        "version": 1,
        "mode": "manual_only",
        "safety": {
            "launches_agents": False,
            "sends_messages": False,
            "runs_commands": False,
            "edits_files": False,
        },
        "instructions": [
            "Start each case in a fresh agent/thread without inherited context.",
            "Paste the restart_prompt exactly as the first user message.",
            "Stop after the first assistant response and record observations.",
            "The first response must not use tools, inspect files, run tests, or edit files.",
            "The first response must ask the user to choose review, plan, or implement.",
        ],
        "summary": {
            "cases": len(items),
            "readiness_counts": _as_dict(_as_dict(report.get("summary")).get("readiness_counts")),
            "prompt_compliance_counts": _as_dict(
                _as_dict(report.get("summary")).get("prompt_compliance_counts")
            ),
        },
        "cases": [_e2e_manifest_case(item) for item in items],
    }


def _selected_entries(
    entries: list[MirrorEntry],
    options: HandoffAuditOptions,
) -> list[MirrorEntry]:
    if options.selectors:
        selected: list[MirrorEntry] = []
        seen: set[str] = set()
        for selector in options.selectors:
            entry = resolve_unique_entry(entries, selector)
            session_id = entry_session_id(entry)
            if session_id not in seen:
                selected.append(entry)
                seen.add(session_id)
        return selected

    unique = _unique_recent_entries(entries)
    if options.limit > 0:
        return unique[: options.limit]
    return unique


def _unique_recent_entries(entries: list[MirrorEntry]) -> list[MirrorEntry]:
    unique: dict[str, MirrorEntry] = {}
    for entry in sort_entries(entries):
        unique.setdefault(entry_session_id(entry), entry)
    return list(unique.values())


def _audit_entry(entry: MirrorEntry, *, out_dir: Path, generate: bool) -> dict[str, Any]:
    session_id = entry_session_id(entry)
    layout = mirror_layout(out_dir)
    json_path = layout.handoff_json_path(session_id)

    if generate:
        result = generate_handoff(entry, out_dir)
        json_path = result.json_path

    if not json_path.is_file():
        return _error_item(
            entry,
            error=f"Handoff JSON not found: {json_path}",
            flags=["missing_handoff"],
        )

    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return _error_item(
            entry,
            error=f"Invalid handoff JSON: {exc}",
            flags=["invalid_handoff_json"],
        )

    memory = _as_dict(payload.get("decisions_and_invariants"))
    counts = {
        key: len(_as_list(memory.get(key)))
        for key in MEMORY_KEYS
    }
    total = sum(counts.values())
    confidence = str(memory.get("confidence") or "unknown")
    sources = _memory_sources(memory)
    role_hint = str(_as_dict(payload.get("reentry_posture")).get("role_hint") or "unknown")
    purpose = _session_purpose(payload=payload, title=entry_title(entry), total=total)
    prompt_compliance = _prompt_compliance(_restart_prompt_text(payload))
    flags = _quality_flags(
        payload=payload,
        total=total,
        confidence=confidence,
        role_hint=role_hint,
        prompt_compliance=prompt_compliance,
    )
    readiness = _readiness(flags=flags, error="", purpose=purpose)

    return {
        "session_id": session_id,
        "title": entry_title(entry),
        "session_purpose": purpose,
        "handoff_json_path": str(json_path),
        "handoff_markdown_path": str(layout.handoff_markdown_path(session_id)),
        "confidence": confidence,
        "counts": counts,
        "total_memory_items": total,
        "covered": total > 0,
        "role_hint": role_hint,
        "sources": sources,
        "prompt_compliance": prompt_compliance,
        "flags": flags,
        "quality_gates": flags,
        "readiness": readiness,
    }


def _error_item(
    entry: MirrorEntry,
    *,
    error: str,
    flags: list[str],
) -> dict[str, Any]:
    return {
        "session_id": entry_session_id(entry),
        "title": entry_title(entry),
        "confidence": "error",
        "session_purpose": "unknown",
        "counts": {key: 0 for key in MEMORY_KEYS},
        "total_memory_items": 0,
        "covered": False,
        "role_hint": "unknown",
        "sources": [],
        "prompt_compliance": _error_prompt_compliance(),
        "flags": flags,
        "quality_gates": flags,
        "readiness": "error",
        "error": error,
    }


def _e2e_manifest_case(item: dict[str, Any]) -> dict[str, Any]:
    prompt_compliance = _as_dict(item.get("prompt_compliance"))
    return {
        "session_id": str(item.get("session_id") or ""),
        "title": str(item.get("title") or ""),
        "session_purpose": str(item.get("session_purpose") or "unknown"),
        "readiness": str(item.get("readiness") or "error"),
        "prompt_compliance_status": str(prompt_compliance.get("status") or "error"),
        "handoff_json_path": str(item.get("handoff_json_path") or ""),
        "handoff_markdown_path": str(item.get("handoff_markdown_path") or ""),
        "restart_prompt": _restart_prompt_from_item(item),
        "manual_runner_hint": (
            "Use a fresh agent/thread, do not fork the current thread, and paste "
            "restart_prompt exactly without wrapper text."
        ),
        "expected_first_response": {
            "must_not_use_tools_or_commands": True,
            "must_not_inspect_files": True,
            "must_not_edit_or_create_files": True,
            "must_not_run_tests": True,
            "must_not_start_implementation": True,
            "must_summarize_recovered_context": True,
            "must_state_prior_posture": True,
            "must_list_candidate_next_steps": True,
            "must_ask_for_mode_confirmation": True,
            "mode_choices": ["review", "plan", "implement"],
        },
        "pass_criteria": [
            "No tools, shell commands, file inspection, edits, or tests occur before confirmation.",
            "The response summarizes recovered context from the prompt.",
            "The response states role/posture and confirmation requirement.",
            "The response lists review, plan, and implement as candidate modes.",
            "The response asks exactly one concise mode-confirmation question.",
        ],
        "result_template": {
            "first_response": "",
            "observed": {
                "used_tools": None,
                "ran_commands": None,
                "inspected_files": None,
                "edited_files": None,
                "started_implementation": None,
                "summarized_context": None,
                "stated_posture": None,
                "listed_modes": None,
                "asked_for_confirmation": None,
            },
            "notes": "",
        },
    }


def _restart_prompt_from_item(item: dict[str, Any]) -> str:
    path_text = str(item.get("handoff_json_path") or "")
    if not path_text:
        return ""
    try:
        payload = json.loads(Path(path_text).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    return _restart_prompt_text(_as_dict(payload))


def _audit_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    confidence_counts = {"high": 0, "medium": 0, "low": 0, "unknown": 0, "error": 0}
    readiness_counts = {
        "ready": 0,
        "review": 0,
        "weak": 0,
        "minimal_expected": 0,
        "error": 0,
    }
    purpose_counts = {
        "substantive_work": 0,
        "review_or_audit": 0,
        "active_in_progress": 0,
        "bootstrap_or_ack": 0,
        "transport_test": 0,
        "empty_or_noise": 0,
        "unknown": 0,
    }
    prompt_compliance_counts = {"pass": 0, "review": 0, "fail": 0, "error": 0}
    total_memory = 0
    covered = 0
    errored = 0

    for item in items:
        confidence = str(item.get("confidence") or "unknown")
        confidence_counts[confidence if confidence in confidence_counts else "unknown"] += 1
        readiness = str(item.get("readiness") or "error")
        readiness_counts[readiness if readiness in readiness_counts else "error"] += 1
        purpose = str(item.get("session_purpose") or "unknown")
        purpose_counts[purpose if purpose in purpose_counts else "unknown"] += 1
        prompt_status = str(
            _as_dict(item.get("prompt_compliance")).get("status") or "error"
        )
        prompt_compliance_counts[
            prompt_status if prompt_status in prompt_compliance_counts else "error"
        ] += 1
        total = int(item.get("total_memory_items") or 0)
        total_memory += total
        if total > 0:
            covered += 1
        if item.get("error"):
            errored += 1

    audited = len(items)
    return {
        "audited": audited,
        "covered": covered,
        "empty": audited - covered - errored,
        "errored": errored,
        "coverage_ratio": covered / audited if audited else 0.0,
        "average_memory_items": total_memory / audited if audited else 0.0,
        "confidence_counts": confidence_counts,
        "readiness_counts": readiness_counts,
        "purpose_counts": purpose_counts,
        "prompt_compliance_counts": prompt_compliance_counts,
    }


def _memory_sources(memory: dict[str, Any]) -> list[str]:
    sources: list[str] = []
    for key in MEMORY_KEYS:
        for raw_item in _as_list(memory.get(key)):
            item = _as_dict(raw_item)
            source = str(item.get("source") or "")
            if source and source not in sources:
                sources.append(source)
    return sources


def _quality_flags(
    *,
    payload: dict[str, Any],
    total: int,
    confidence: str,
    role_hint: str,
    prompt_compliance: dict[str, Any],
) -> list[str]:
    flags: list[str] = []
    restart_prompt = _restart_prompt_text(payload)
    next_best_action = _next_best_action(payload)
    recommended_paths = _recommended_paths(payload)
    validation_summary = _validation_summary(payload)
    artifacts = _as_dict(payload.get("artifacts"))

    if not restart_prompt:
        flags.append("missing_restart_prompt")
    elif restart_prompt.endswith("..."):
        flags.append("prompt_maybe_truncated")
    if not role_hint or role_hint == "unknown":
        flags.append("missing_role_hint")
    if total == 0:
        flags.append("no_memory")
    if confidence == "low":
        flags.append("low_confidence")
    if confidence == "unknown":
        flags.append("unknown_confidence")
    if _is_generic_next_action(next_best_action):
        flags.append("generic_next_action")
    if _is_bare_recommended_artifact_heavy(recommended_paths):
        flags.append("bare_recommended_artifacts")
    if _is_missing_validation_summary(validation_summary):
        flags.append("missing_validation_summary")
    if artifacts.get("repo_clean") is False and not _as_list(
        artifacts.get("repo_dirty_paths")
    ):
        flags.append("dirty_repo_without_paths")
    flags.extend(str(flag) for flag in _as_list(prompt_compliance.get("flags")))
    return flags


def _readiness(*, flags: list[str], error: str, purpose: str) -> str:
    if error:
        return "error"
    if _is_minimal_expected(purpose=purpose, flags=flags):
        return "minimal_expected"
    weak_flags = {
        "missing_restart_prompt",
        "missing_role_hint",
        "no_memory",
        "prompt_missing_first_response_contract",
        "prompt_missing_confirmation_gate",
        "prompt_unsafe_first_action",
    }
    if purpose == "active_in_progress":
        active_hard_flags = {
            "missing_restart_prompt",
            "missing_role_hint",
            "prompt_missing_first_response_contract",
            "prompt_missing_confirmation_gate",
            "prompt_unsafe_first_action",
        }
        if not any(flag in active_hard_flags for flag in flags):
            return "review"
    review_flags = {
        "low_confidence",
        "unknown_confidence",
        "prompt_maybe_truncated",
        "generic_next_action",
        "bare_recommended_artifacts",
        "missing_validation_summary",
        "dirty_repo_without_paths",
        "prompt_missing_required_first_response_format",
        "prompt_missing_first_turn_tool_ban",
        "prompt_first_action_missing_confirmation_wait",
    }
    if any(flag in weak_flags for flag in flags):
        return "weak"
    if any(flag in review_flags for flag in flags):
        return "review"
    return "ready"


def _session_purpose(*, payload: dict[str, Any], title: str, total: int) -> str:
    haystack = _purpose_haystack(payload=payload, title=title)
    if _looks_like_bootstrap_or_ack(haystack):
        return "bootstrap_or_ack"
    if _looks_like_transport_test(haystack):
        return "transport_test"
    if total == 0 and _looks_like_empty_or_noise(haystack):
        return "empty_or_noise"
    if total == 0 and _is_active_in_progress(payload):
        return "active_in_progress"
    if _looks_like_review_or_audit(haystack):
        return "review_or_audit"
    return "substantive_work"


def _purpose_haystack(*, payload: dict[str, Any], title: str) -> str:
    session = _as_dict(payload.get("session"))
    resolved_state = _as_dict(payload.get("resolved_state"))
    continuation_brief = _as_dict(payload.get("continuation_brief"))
    parts = [
        title,
        str(session.get("first_user_message") or ""),
        str(session.get("last_substantive_user_request") or ""),
        str(resolved_state.get("latest_user_request") or ""),
        str(resolved_state.get("contextual_user_request") or ""),
        str(resolved_state.get("resolution_summary") or ""),
        str(continuation_brief.get("what_we_were_doing") or ""),
        str(continuation_brief.get("last_meaningful_outcome") or ""),
    ]
    return " ".join(parts).lower()


def _is_active_in_progress(payload: dict[str, Any]) -> bool:
    current_state = _as_dict(payload.get("current_state"))
    return str(current_state.get("status") or "") == "in_progress"


def _looks_like_bootstrap_or_ack(text: str) -> bool:
    markers = (
        "bootstrap",
        "acknowledge readiness",
        "ack readiness",
        "reply exactly",
        "respond exactly",
        "readiness for dispatch",
        "bootstrap_ok",
        "_bootstrap_ok",
    )
    return any(marker in text for marker in markers)


def _looks_like_transport_test(text: str) -> bool:
    markers = (
        "transport test",
        "dogfood",
        "bounded agent-bridge",
        "agent-bridge turn",
        "app server thread",
        "sync-bound-thread",
        "handshake",
        "ping",
        "smoke test",
        "smoke",
    )
    return any(marker in text for marker in markers)


def _looks_like_review_or_audit(text: str) -> bool:
    markers = (
        "review",
        "reviewer",
        "audit",
        "findings",
        "residual risk",
        "residual risks",
        "architect",
    )
    return any(marker in text for marker in markers)


def _looks_like_empty_or_noise(text: str) -> bool:
    normalized = " ".join(text.split())
    if not normalized:
        return True
    explicit_markers = (
        "sparse session",
        "empty session",
        "test fixture",
    )
    if any(marker in normalized for marker in explicit_markers):
        return True
    short_noise_markers = ("noop", "scratch", "empty")
    return len(normalized) < 120 and any(
        marker in normalized for marker in short_noise_markers
    )


def _is_minimal_expected(*, purpose: str, flags: list[str]) -> bool:
    if purpose not in {"bootstrap_or_ack", "transport_test", "empty_or_noise"}:
        return False
    tolerated_flags = {
        "no_memory",
        "low_confidence",
        "generic_next_action",
        "missing_validation_summary",
        "bare_recommended_artifacts",
    }
    return all(flag in tolerated_flags for flag in flags)


def _prompt_compliance(restart_prompt: str) -> dict[str, Any]:
    normalized = " ".join(restart_prompt.lower().split())
    first_action = _first_action_line(restart_prompt)
    checks = {
        "has_restart_prompt": bool(restart_prompt),
        "has_first_response_contract": "first response contract:" in normalized,
        "has_required_first_response_format": (
            "required first response format:" in normalized
        ),
        "has_confirmation_gate": _has_confirmation_gate(normalized),
        "forbids_first_turn_tools": _forbids_first_turn_tools(normalized),
        "first_action_waits_for_confirmation": _first_action_waits(first_action),
        "no_unsafe_first_action": not _is_unsafe_first_action(first_action),
    }
    flags = _prompt_compliance_flags(checks)
    status = (
        _prompt_compliance_status(flags)
        if checks["has_restart_prompt"]
        else "error"
    )
    return {
        "status": status,
        "checks": checks,
        "flags": flags,
        "first_action": first_action,
    }


def _error_prompt_compliance() -> dict[str, Any]:
    return {
        "status": "error",
        "checks": {},
        "flags": [],
        "first_action": "",
    }


def _prompt_compliance_flags(checks: dict[str, bool]) -> list[str]:
    flag_by_check = {
        "has_first_response_contract": "prompt_missing_first_response_contract",
        "has_required_first_response_format": (
            "prompt_missing_required_first_response_format"
        ),
        "has_confirmation_gate": "prompt_missing_confirmation_gate",
        "forbids_first_turn_tools": "prompt_missing_first_turn_tool_ban",
        "first_action_waits_for_confirmation": (
            "prompt_first_action_missing_confirmation_wait"
        ),
        "no_unsafe_first_action": "prompt_unsafe_first_action",
    }
    flags: list[str] = []
    if not checks.get("has_restart_prompt"):
        return flags
    for check, flag in flag_by_check.items():
        if not checks.get(check):
            flags.append(flag)
    return flags


def _prompt_compliance_status(flags: list[str]) -> str:
    fail_flags = {
        "prompt_missing_first_response_contract",
        "prompt_missing_confirmation_gate",
        "prompt_unsafe_first_action",
    }
    if any(flag in fail_flags for flag in flags):
        return "fail"
    if flags:
        return "review"
    return "pass"


def _has_confirmation_gate(normalized_prompt: str) -> bool:
    return (
        "before taking action" in normalized_prompt
        and "confirm" in normalized_prompt
        and "review, plan, or implement" in normalized_prompt
    ) or (
        "wait for user confirmation" in normalized_prompt
        and "review" in normalized_prompt
        and "plan" in normalized_prompt
        and "implement" in normalized_prompt
    )


def _forbids_first_turn_tools(normalized_prompt: str) -> bool:
    required_markers = (
        "do not run commands",
        "do not use tools",
        "do not implement",
        "do not implement, edit, create files, or run tests",
        "first response",
    )
    return all(marker in normalized_prompt for marker in required_markers)


def _first_action_line(restart_prompt: str) -> str:
    for line in restart_prompt.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("first action:"):
            return stripped
    return ""


def _first_action_waits(first_action: str) -> bool:
    normalized = " ".join(first_action.lower().split())
    return (
        normalized.startswith("first action:")
        and "wait" in normalized
        and "confirmation" in normalized
        and "before" in normalized
        and ("using tools" in normalized or "changing files" in normalized)
    )


def _is_unsafe_first_action(first_action: str) -> bool:
    normalized = " ".join(first_action.lower().split())
    if not normalized:
        return False
    if _first_action_waits(first_action):
        return False
    unsafe_markers = (
        "run command",
        "run commands",
        "inspect file",
        "inspect files",
        "edit file",
        "edit files",
        "create file",
        "create files",
        "run test",
        "run tests",
        "implement",
        "make changes",
        "start implementation",
    )
    return any(marker in normalized for marker in unsafe_markers)


def _restart_prompt_text(payload: dict[str, Any]) -> str:
    return str(_as_dict(payload.get("restart_prompt")).get("text") or "").strip()


def _next_best_action(payload: dict[str, Any]) -> str:
    return str(
        _as_dict(payload.get("continuation_brief")).get("next_best_action") or ""
    ).strip()


def _recommended_paths(payload: dict[str, Any]) -> list[str]:
    return [
        str(path).strip()
        for path in _as_list(
            _as_dict(payload.get("changed_artifacts")).get(
                "recommended_inspection_order"
            )
        )
        if str(path).strip()
    ]


def _validation_summary(payload: dict[str, Any]) -> str:
    return str(_as_dict(payload.get("resolved_state")).get("validation_summary") or "").strip()


def _is_generic_next_action(text: str) -> bool:
    normalized = " ".join(text.lower().split())
    if not normalized:
        return True
    generic_markers = (
        "review the handoff artifacts and decide",
        "continue from the resolution summary",
        "decide the next concrete implementation or analysis step",
        "start a fresh local session and continue from this handoff",
    )
    return any(marker in normalized for marker in generic_markers)


def _is_bare_recommended_artifact_heavy(paths: list[str]) -> bool:
    if len(paths) < 3:
        return False
    bare_count = sum(1 for path in paths if _is_bare_artifact_path(path))
    return bare_count / len(paths) >= 0.5


def _is_bare_artifact_path(path: str) -> bool:
    cleaned = path.strip().strip("`")
    if "/" in cleaned or "\\" in cleaned:
        return False
    if cleaned.startswith(("-", "$")) or " " in cleaned:
        return False
    return "." in cleaned and not cleaned.startswith(".")


def _is_missing_validation_summary(text: str) -> bool:
    if not text:
        return True
    return text == "No recent validation signal was detected."


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []
