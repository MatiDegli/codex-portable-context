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
    flags = _quality_flags(
        payload=payload,
        total=total,
        confidence=confidence,
        role_hint=role_hint,
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
        "flags": flags,
        "quality_gates": flags,
        "readiness": "error",
        "error": error,
    }


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
    }
    if purpose == "active_in_progress":
        active_hard_flags = {
            "missing_restart_prompt",
            "missing_role_hint",
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
    if _looks_like_review_or_audit(haystack):
        return "review_or_audit"
    if total == 0 and _looks_like_empty_or_noise(haystack):
        return "empty_or_noise"
    if total == 0 and _is_active_in_progress(payload):
        return "active_in_progress"
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
    resolved_state = _as_dict(payload.get("resolved_state"))
    return (
        str(current_state.get("status") or "") == "in_progress"
        and str(resolved_state.get("request_resolution_status") or "") == "unanswered"
    )


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
