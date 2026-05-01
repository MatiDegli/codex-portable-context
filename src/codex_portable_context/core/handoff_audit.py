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
            "Readiness: ready={ready}, review={review}, weak={weak}, error={error}."
        ).format(
            ready=summary.get("readiness_counts", {}).get("ready", 0),
            review=summary.get("readiness_counts", {}).get("review", 0),
            weak=summary.get("readiness_counts", {}).get("weak", 0),
            error=summary.get("readiness_counts", {}).get("error", 0),
        ),
        "",
        (
            f"{'SESSION':<8}  {'TITLE':<32}  {'READY':<6}  {'CONF':<6}  "
            f"{'D':>2} {'I':>2} {'R':>2} {'O':>2}  {'ROLE':<18}  "
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
            f"{truncate(str(item.get('title') or ''), 32):<32}  "
            f"{str(item.get('readiness') or 'error'):<6}  "
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
    flags = _quality_flags(
        payload=payload,
        total=total,
        confidence=confidence,
        role_hint=role_hint,
    )
    readiness = _readiness(flags=flags, error="")

    return {
        "session_id": session_id,
        "title": entry_title(entry),
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
    readiness_counts = {"ready": 0, "review": 0, "weak": 0, "error": 0}
    total_memory = 0
    covered = 0
    errored = 0

    for item in items:
        confidence = str(item.get("confidence") or "unknown")
        confidence_counts[confidence if confidence in confidence_counts else "unknown"] += 1
        readiness = str(item.get("readiness") or "error")
        readiness_counts[readiness if readiness in readiness_counts else "error"] += 1
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


def _readiness(*, flags: list[str], error: str) -> str:
    if error:
        return "error"
    weak_flags = {
        "missing_restart_prompt",
        "missing_role_hint",
        "no_memory",
    }
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
