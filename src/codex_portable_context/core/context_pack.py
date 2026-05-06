"""Derived multi-session context packs for downstream roadmap planners."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .discovery import mirror_layout
from .handoff_audit import _prompt_compliance, _source_contract_compliance
from .index import MirrorEntry, entry_session_id, entry_title, sort_entries
from .listing import truncate

CONTEXT_PACK_KIND = "codex_multi_session_context_pack"
CONTEXT_PACK_SCHEMA_VERSION = 1
WORKSTATION_ROADMAP_CONTRACT = "roadmap_decomposition_context_pack_v1"
DEFAULT_SECTION_ITEM_LIMIT = 8
SUMMARY_STATUS_VALUES = ("pass", "review", "fail", "error")


@dataclass(frozen=True, slots=True)
class ContextPackOptions:
    """Selection and shaping options for a derived context pack."""

    latest: int = 5
    repo_root: str = ""
    provider: str = ""
    session_ids: tuple[str, ...] = ()
    query: str = ""
    since: str = ""
    until: str = ""
    require_redacted: bool = False
    section_item_limit: int = DEFAULT_SECTION_ITEM_LIMIT


def build_context_pack(
    entries: list[MirrorEntry],
    *,
    out_dir: Path,
    options: ContextPackOptions,
) -> dict[str, Any]:
    """Build a provider-neutral manifest from existing derived handoff JSON files."""

    layout = mirror_layout(out_dir)
    unique_entries = _unique_recent_entries(entries)
    missing_handoffs: list[dict[str, Any]] = []
    invalid_handoffs: list[dict[str, Any]] = []
    filtered_counts: dict[str, int] = {}
    candidates: list[dict[str, Any]] = []

    for entry in unique_entries:
        session_id = entry_session_id(entry)
        handoff_path = layout.handoff_json_path(session_id)
        if not handoff_path.is_file():
            entry_filter_reason = _entry_filter_reason(entry, options)
            if entry_filter_reason:
                filtered_counts[entry_filter_reason] = (
                    filtered_counts.get(entry_filter_reason, 0) + 1
                )
                continue
            missing_handoffs.append(
                _skipped_session(entry, reason="missing_handoff_json", path=handoff_path)
            )
            continue

        try:
            payload = json.loads(handoff_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            invalid_handoffs.append(
                _skipped_session(
                    entry,
                    reason="invalid_handoff_json",
                    path=handoff_path,
                    error=str(exc),
                )
            )
            continue

        filter_reason = _filter_reason(entry, payload, options)
        if filter_reason:
            filtered_counts[filter_reason] = filtered_counts.get(filter_reason, 0) + 1
            continue

        candidates.append(
            _session_item(
                entry,
                payload=payload,
                handoff_path=handoff_path,
                out_dir=layout.out_dir,
                options=options,
            )
        )

    ordered_candidates = _sort_candidates(candidates, options=options)
    included = ordered_candidates
    limited_out = 0
    if options.latest > 0:
        included = ordered_candidates[: options.latest]
        limited_out = max(0, len(ordered_candidates) - len(included))

    if limited_out:
        filtered_counts["outside_latest_limit"] = (
            filtered_counts.get("outside_latest_limit", 0) + limited_out
        )

    return {
        "kind": CONTEXT_PACK_KIND,
        "schema_version": CONTEXT_PACK_SCHEMA_VERSION,
        "status": "ready" if included else "blocked",
        "contract": WORKSTATION_ROADMAP_CONTRACT,
        "contract_id": WORKSTATION_ROADMAP_CONTRACT,
        "advisory_only": True,
        "generated_at": _iso_now(),
        "mode": "derived_handoff_manifest",
        "authority_boundary": {
            "repo_local_authoritative": False,
            "historical_context_advisory": True,
            "live_resume": False,
            "raw_transcript_included": False,
            "transcript_excerpt_included": False,
            "reads_provider_raw_state": False,
            "moves_auth_config_runtime_state": False,
        },
        "selection": {
            "out_dir": str(layout.out_dir),
            "repo_root": _normalized_path_filter(options.repo_root),
            "provider": options.provider,
            "latest": options.latest,
            "session_ids": list(options.session_ids),
            "query": options.query,
            "since": options.since,
            "until": options.until,
            "require_redacted": options.require_redacted,
            "section_item_limit": options.section_item_limit,
            "source_scope": "existing_derived_handoffs_only",
        },
        "expected_handoff_dir": str(layout.handoffs_dir),
        "selected_session_count": len(included),
        "redaction_mode": _redaction_mode(included),
        "source_hashes": _manifest_source_hashes(included),
        "summary": _summary(
            total_entries=len(unique_entries),
            loaded_candidates=len(candidates),
            included=included,
            missing_handoffs=missing_handoffs,
            invalid_handoffs=invalid_handoffs,
            filtered_counts=filtered_counts,
        ),
        "sessions": included,
        "skipped_sessions": {
            "missing_handoff_json": missing_handoffs[:20],
            "invalid_handoff_json": invalid_handoffs[:20],
            "filtered_counts": filtered_counts,
        },
        "limitations": _manifest_limitations(),
        "preflight": _preflight(
            expected_handoff_dir=layout.handoffs_dir,
            included=included,
            missing_handoffs=missing_handoffs,
            invalid_handoffs=invalid_handoffs,
            unresolved_selectors=_unresolved_selectors(unique_entries, options),
        ),
        "audit": {
            "derived_only": True,
            "raw_transcript_excluded": True,
            "source_hash_scope": "derived_artifacts_only",
            "prompt_compliance_counts": _status_counts(
                _as_dict(_as_dict(item.get("audit")).get("prompt_compliance")).get("status")
                for item in included
            ),
            "source_contract_counts": _status_counts(
                _as_dict(_as_dict(item.get("audit")).get("source_contract_compliance")).get(
                    "status"
                )
                for item in included
            ),
        },
    }


def build_context_pack_error(
    *,
    out_dir: Path,
    blocked_reason: str,
    repair_guidance: list[str],
    detail: str = "",
) -> dict[str, Any]:
    """Build a structured context-pack error response."""

    layout = mirror_layout(out_dir)
    return {
        "kind": CONTEXT_PACK_KIND,
        "schema_version": CONTEXT_PACK_SCHEMA_VERSION,
        "status": "blocked",
        "contract": WORKSTATION_ROADMAP_CONTRACT,
        "contract_id": WORKSTATION_ROADMAP_CONTRACT,
        "advisory_only": True,
        "generated_at": _iso_now(),
        "mode": "derived_handoff_manifest",
        "blocked_reason": blocked_reason,
        "repair_guidance": repair_guidance,
        "expected_handoff_dir": str(layout.handoffs_dir),
        "detail": detail,
        "authority_boundary": {
            "repo_local_authoritative": False,
            "historical_context_advisory": True,
            "live_resume": False,
            "raw_transcript_included": False,
            "transcript_excerpt_included": False,
            "reads_provider_raw_state": False,
            "moves_auth_config_runtime_state": False,
        },
    }


def build_context_pack_blocked_response(manifest: dict[str, Any]) -> dict[str, Any]:
    """Build a structured blocked response from an empty context-pack manifest."""

    preflight = _as_dict(manifest.get("preflight"))
    return {
        "kind": CONTEXT_PACK_KIND,
        "schema_version": CONTEXT_PACK_SCHEMA_VERSION,
        "status": "blocked",
        "contract": WORKSTATION_ROADMAP_CONTRACT,
        "contract_id": WORKSTATION_ROADMAP_CONTRACT,
        "advisory_only": True,
        "generated_at": _iso_now(),
        "mode": "derived_handoff_manifest",
        "blocked_reason": _string(preflight.get("blocked_reason")) or "no_matching_handoffs",
        "repair_guidance": _as_list(preflight.get("repair_guidance")),
        "expected_handoff_dir": _string(manifest.get("expected_handoff_dir")),
        "selection": _as_dict(manifest.get("selection")),
        "summary": _as_dict(manifest.get("summary")),
        "skipped_sessions": _as_dict(manifest.get("skipped_sessions")),
        "preflight": preflight,
        "limitations": _as_list(manifest.get("limitations")),
        "authority_boundary": _as_dict(manifest.get("authority_boundary")),
    }


def build_context_pack_preflight_response(manifest: dict[str, Any]) -> dict[str, Any]:
    """Build a compact preflight response from a context-pack manifest."""

    preflight = _as_dict(manifest.get("preflight"))
    return {
        "kind": "codex_multi_session_context_pack_preflight",
        "schema_version": CONTEXT_PACK_SCHEMA_VERSION,
        "status": _string(preflight.get("status")) or "blocked",
        "contract": WORKSTATION_ROADMAP_CONTRACT,
        "contract_id": WORKSTATION_ROADMAP_CONTRACT,
        "advisory_only": True,
        "generated_at": _iso_now(),
        "mode": "derived_handoff_preflight",
        "blocked_reason": _string(preflight.get("blocked_reason")),
        "repair_guidance": _as_list(preflight.get("repair_guidance")),
        "expected_handoff_dir": _string(manifest.get("expected_handoff_dir")),
        "selection": _as_dict(manifest.get("selection")),
        "summary": _as_dict(manifest.get("summary")),
        "preflight": preflight,
        "authority_boundary": _as_dict(manifest.get("authority_boundary")),
    }


def render_context_pack_summary(manifest: dict[str, Any]) -> str:
    """Render a compact human-readable context pack summary."""

    summary = _as_dict(manifest.get("summary"))
    selection = _as_dict(manifest.get("selection"))
    lines = [
        (
            "Context pack: {included} included session(s), {candidates} matching "
            "candidate(s), {total} indexed session(s)."
        ).format(
            included=summary.get("included_sessions", 0),
            candidates=summary.get("matching_candidates", 0),
            total=summary.get("indexed_sessions", 0),
        ),
        (
            "Scope: repo_root={repo_root}, provider={provider}, latest={latest}, "
            "derived-only=yes."
        ).format(
            repo_root=selection.get("repo_root") or "*",
            provider=selection.get("provider") or "*",
            latest=selection.get("latest", 0),
        ),
        (
            "Audit: prompt pass={prompt_pass}, source pass={source_pass}, "
            "missing handoffs={missing}, invalid handoffs={invalid}."
        ).format(
            prompt_pass=summary.get("prompt_compliance_counts", {}).get("pass", 0),
            source_pass=summary.get("source_contract_counts", {}).get("pass", 0),
            missing=summary.get("missing_handoff_json", 0),
            invalid=summary.get("invalid_handoff_json", 0),
        ),
        "",
        f"{'SESSION':<8}  {'TITLE':<32}  {'PROVIDER':<12}  {'UPDATED':<20}  SCORE  REASONS",
    ]
    for raw_item in _as_list(manifest.get("sessions")):
        item = _as_dict(raw_item)
        ranking = _as_dict(item.get("ranking"))
        reasons = ", ".join(str(reason) for reason in _as_list(ranking.get("reasons"))) or "-"
        lines.append(
            f"{str(item.get('session_id') or '')[:8]:<8}  "
            f"{truncate(str(item.get('title') or ''), 32):<32}  "
            f"{truncate(str(item.get('provider') or ''), 12):<12}  "
            f"{truncate(str(item.get('updated_at') or ''), 20):<20}  "
            f"{float(ranking.get('score') or 0.0):>5.1f}  "
            f"{truncate(reasons, 52)}"
        )
    return "\n".join(lines) + "\n"


def write_context_pack(manifest: dict[str, Any], path: Path) -> Path:
    """Write a context pack manifest to disk."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def _session_item(
    entry: MirrorEntry,
    *,
    payload: dict[str, Any],
    handoff_path: Path,
    out_dir: Path,
    options: ContextPackOptions,
) -> dict[str, Any]:
    artifacts = _as_dict(payload.get("artifacts"))
    source = _as_dict(payload.get("source_availability"))
    prompt_compliance = _prompt_compliance(_restart_prompt_text(payload))
    source_contract = _source_contract_compliance(payload)
    ranking = _ranking(entry, payload, options=options)
    limitations = _session_limitations(
        payload=payload,
        prompt_compliance=prompt_compliance,
        source_contract=source_contract,
    )
    metadata_path = _derived_path(out_dir, _entry_or_artifact_relpath(entry, artifacts, "metadata"))
    handoff_markdown_path = _derived_path(
        out_dir,
        _string(artifacts.get("handoff_markdown_relpath")),
    )
    return {
        "session_id": _string(payload.get("session_id")) or entry_session_id(entry),
        "provider": _string(payload.get("provider")) or _string(entry.get("provider")) or "unknown",
        "provider_session_id": _string(payload.get("provider_session_id")),
        "title": _string(payload.get("title")) or entry_title(entry),
        "updated_at": _string(payload.get("updated_at")) or _string(entry.get("updated_at")),
        "session_timestamp": _string(payload.get("session_timestamp")),
        "repo_root": _string(artifacts.get("repo_root")) or _string(entry.get("cwd")),
        "repo_branch": _string(artifacts.get("repo_branch")),
        "repo_head_commit": _string(artifacts.get("repo_head_commit")),
        "repo_clean": artifacts.get("repo_clean"),
        "redacted": bool(payload.get("redacted") or entry.get("redacted")),
        "redaction_status": _redaction_status(entry, payload),
        "source_hashes": _source_hashes(
            handoff_json_path=handoff_path,
            handoff_markdown_path=handoff_markdown_path,
            metadata_path=metadata_path,
        ),
        "source_paths": {
            "handoff_json_relpath": _relative_to(handoff_path, out_dir),
            "handoff_markdown_relpath": _relative_to(handoff_markdown_path, out_dir),
            "metadata_relpath": _relative_to(metadata_path, out_dir),
        },
        "available_sections": _as_dict(source.get("available_sections")),
        "section_sources": _as_dict(source.get("section_sources")),
        "source_availability": {
            "provider": _string(source.get("provider")),
            "mode": _string(source.get("mode")),
            "available": source.get("available"),
            "exact_recent_window": source.get("exact_recent_window"),
            "limitations": _as_list(source.get("limitations")),
            "note": _string(source.get("note")),
        },
        "section_presence": _section_presence(payload),
        "sections": _sections(payload, limit=options.section_item_limit),
        "ranking": ranking,
        "audit": {
            "prompt_compliance": prompt_compliance,
            "source_contract_compliance": source_contract,
        },
        "limitations": limitations,
    }


def _sections(payload: dict[str, Any], *, limit: int) -> dict[str, Any]:
    memory = _as_dict(payload.get("decisions_and_invariants"))
    changed = _as_dict(payload.get("changed_artifacts"))
    return {
        "continuation_brief": _only_keys(
            _as_dict(payload.get("continuation_brief")),
            (
                "what_we_were_doing",
                "latest_resolved_request",
                "last_meaningful_outcome",
                "next_best_action",
                "confidence",
            ),
        ),
        "resolved_state": _only_keys(
            _as_dict(payload.get("resolved_state")),
            (
                "latest_user_request",
                "request_resolution_status",
                "resolution_summary",
                "validation_summary",
                "dirty_state_summary",
            ),
        ),
        "decisions_and_invariants": {
            "confidence": _string(memory.get("confidence")),
            "counts": {
                "decisions": len(_as_list(memory.get("decisions"))),
                "invariants": len(_as_list(memory.get("invariants"))),
                "rejected_paths": len(_as_list(memory.get("rejected_paths"))),
                "open_architecture_questions": len(
                    _as_list(memory.get("open_architecture_questions"))
                ),
            },
            "decisions": _limited_list(memory.get("decisions"), limit=limit),
            "invariants": _limited_list(memory.get("invariants"), limit=limit),
            "rejected_paths": _limited_list(memory.get("rejected_paths"), limit=limit),
            "open_architecture_questions": _limited_list(
                memory.get("open_architecture_questions"),
                limit=limit,
            ),
        },
        "open_loops": _as_dict(payload.get("open_loops")),
        "changed_artifacts": {
            "summary": _string(changed.get("summary")),
            "counts": {
                "changed_paths": len(_as_list(changed.get("changed_paths"))),
                "key_paths": len(_as_list(changed.get("key_paths"))),
                "recommended_inspection_order": len(
                    _as_list(changed.get("recommended_inspection_order"))
                ),
            },
            "changed_paths": _limited_list(changed.get("changed_paths"), limit=limit),
            "key_paths": _limited_list(changed.get("key_paths"), limit=limit),
            "recommended_inspection_order": _limited_list(
                changed.get("recommended_inspection_order"),
                limit=limit,
            ),
        },
        "roadmap_evidence": _evidence_section(payload.get("roadmap_evidence"), limit=limit),
        "repo_evidence": _evidence_section(payload.get("repo_evidence"), limit=limit),
    }


def _evidence_section(value: Any, *, limit: int) -> dict[str, Any]:
    evidence = _as_dict(value)
    sources = _as_list(evidence.get("sources"))
    return {
        "status": _string(evidence.get("status")),
        "summary": _string(evidence.get("summary")),
        "include_in_restart_prompt": evidence.get("include_in_restart_prompt"),
        "used_for_synthesis": evidence.get("used_for_synthesis"),
        "recommended_inspection_order": _limited_list(
            evidence.get("recommended_inspection_order"),
            limit=limit,
        ),
        "sources": [_compact_source(_as_dict(source)) for source in sources[:limit]],
        "sources_count": len(sources),
        "truncated": len(sources) > limit,
    }


def _compact_source(source: dict[str, Any]) -> dict[str, Any]:
    return {
        key: source[key]
        for key in ("path", "kind", "confidence", "include_in_restart_prompt", "source")
        if key in source
    }


def _section_presence(payload: dict[str, Any]) -> dict[str, Any]:
    memory = _as_dict(payload.get("decisions_and_invariants"))
    changed = _as_dict(payload.get("changed_artifacts"))
    open_loops = _as_dict(payload.get("open_loops"))
    return {
        "decisions": len(_as_list(memory.get("decisions"))),
        "invariants": len(_as_list(memory.get("invariants"))),
        "rejected_paths": len(_as_list(memory.get("rejected_paths"))),
        "open_architecture_questions": len(_as_list(memory.get("open_architecture_questions"))),
        "open_loops": {
            key: bool(_string(value)) and _string(value).lower() != "none"
            for key, value in open_loops.items()
        },
        "changed_paths": len(_as_list(changed.get("changed_paths"))),
        "key_paths": len(_as_list(changed.get("key_paths"))),
        "recommended_inspection_order": len(_as_list(changed.get("recommended_inspection_order"))),
    }


def _filter_reason(
    entry: MirrorEntry,
    payload: dict[str, Any],
    options: ContextPackOptions,
) -> str:
    session_id = _string(payload.get("session_id")) or entry_session_id(entry)
    if options.session_ids and not any(
        _selector_matches(session_id, selector) for selector in options.session_ids
    ):
        return "session_id_filter"

    if options.provider:
        provider = (_string(payload.get("provider")) or _string(entry.get("provider"))).lower()
        if provider != options.provider.lower():
            return "provider_filter"

    if options.repo_root:
        repo_root = _session_repo_root(payload, entry)
        if _normalized_path_filter(repo_root) != _normalized_path_filter(options.repo_root):
            return "repo_root_filter"

    timestamp = _session_timestamp(payload, entry)
    if options.since and not _timestamp_at_or_after(timestamp, options.since):
        return "since_filter"
    if options.until and not _timestamp_at_or_before(timestamp, options.until):
        return "until_filter"

    if options.require_redacted and not bool(payload.get("redacted") or entry.get("redacted")):
        return "require_redacted_filter"

    if options.query and _query_score(payload, entry, options.query) <= 0:
        return "query_filter"

    return ""


def _entry_filter_reason(entry: MirrorEntry, options: ContextPackOptions) -> str:
    """Return a safe pre-handoff filter reason for missing-handoff candidates."""

    session_id = entry_session_id(entry)
    if options.session_ids and not any(
        _selector_matches(session_id, selector) for selector in options.session_ids
    ):
        return "session_id_filter"

    if options.provider:
        provider = _string(entry.get("provider")).lower()
        if provider and provider != options.provider.lower():
            return "provider_filter"

    if options.repo_root:
        cwd = _string(entry.get("cwd"))
        if cwd and _normalized_path_filter(cwd) != _normalized_path_filter(options.repo_root):
            return "repo_root_filter"

    timestamp = _string(entry.get("updated_at")) or _string(entry.get("session_timestamp"))
    if options.since and timestamp and not _timestamp_at_or_after(timestamp, options.since):
        return "since_filter"
    if options.until and timestamp and not _timestamp_at_or_before(timestamp, options.until):
        return "until_filter"

    if options.require_redacted and entry.get("redacted") is False:
        return "require_redacted_filter"

    return ""


def _ranking(
    entry: MirrorEntry,
    payload: dict[str, Any],
    *,
    options: ContextPackOptions,
) -> dict[str, Any]:
    score = 0.0
    reasons: list[str] = []
    session_id = _string(payload.get("session_id")) or entry_session_id(entry)

    if any(_selector_matches(session_id, selector) for selector in options.session_ids):
        score += 100.0
        reasons.append("explicit_session_id_match")
    if options.repo_root and _normalized_path_filter(
        _session_repo_root(payload, entry)
    ) == _normalized_path_filter(options.repo_root):
        score += 50.0
        reasons.append("repo_root_match")
    provider = (_string(payload.get("provider")) or _string(entry.get("provider"))).lower()
    if options.provider and provider == options.provider.lower():
        score += 10.0
        reasons.append("provider_match")

    query_score = _query_score(payload, entry, options.query)
    if query_score:
        score += min(30.0, float(query_score * 5))
        reasons.append("query_match")

    memory_total = sum(
        len(_as_list(_as_dict(payload.get("decisions_and_invariants")).get(key)))
        for key in (
            "decisions",
            "invariants",
            "rejected_paths",
            "open_architecture_questions",
        )
    )
    if memory_total:
        score += min(10.0, float(memory_total))
        reasons.append("memory_available")

    prompt_status = _prompt_compliance(_restart_prompt_text(payload)).get("status")
    if prompt_status == "pass":
        score += 5.0
        reasons.append("prompt_compliance_pass")
    source_status = _source_contract_compliance(payload).get("status")
    if source_status == "pass":
        score += 5.0
        reasons.append("source_contract_pass")

    if not reasons:
        reasons.append("latest_after_filters")

    return {
        "score": round(score, 2),
        "reasons": reasons,
        "updated_at_sort_key": _session_timestamp(payload, entry),
    }


def _sort_candidates(
    candidates: list[dict[str, Any]],
    *,
    options: ContextPackOptions,
) -> list[dict[str, Any]]:
    def sort_key(item: dict[str, Any]) -> tuple[float, str]:
        ranking = _as_dict(item.get("ranking"))
        timestamp = _string(ranking.get("updated_at_sort_key"))
        score = float(ranking.get("score") or 0.0)
        if options.query:
            return (score, timestamp)
        return (_timestamp_score(timestamp), f"{score:012.2f}")

    return sorted(candidates, key=sort_key, reverse=True)


def _summary(
    *,
    total_entries: int,
    loaded_candidates: int,
    included: list[dict[str, Any]],
    missing_handoffs: list[dict[str, Any]],
    invalid_handoffs: list[dict[str, Any]],
    filtered_counts: dict[str, int],
) -> dict[str, Any]:
    return {
        "indexed_sessions": total_entries,
        "matching_candidates": loaded_candidates,
        "included_sessions": len(included),
        "selected_session_count": len(included),
        "missing_handoff_json": len(missing_handoffs),
        "invalid_handoff_json": len(invalid_handoffs),
        "filtered_counts": filtered_counts,
        "providers": sorted(
            {
                _string(item.get("provider"))
                for item in included
                if _string(item.get("provider"))
            }
        ),
        "redaction_counts": {
            "redacted": sum(1 for item in included if item.get("redacted") is True),
            "not_redacted": sum(1 for item in included if item.get("redacted") is not True),
        },
        "prompt_compliance_counts": _status_counts(
            _as_dict(_as_dict(item.get("audit")).get("prompt_compliance")).get("status")
            for item in included
        ),
        "source_contract_counts": _status_counts(
            _as_dict(_as_dict(item.get("audit")).get("source_contract_compliance")).get("status")
            for item in included
        ),
    }


def _preflight(
    *,
    expected_handoff_dir: Path,
    included: list[dict[str, Any]],
    missing_handoffs: list[dict[str, Any]],
    invalid_handoffs: list[dict[str, Any]],
    unresolved_selectors: list[str],
) -> dict[str, Any]:
    ready = bool(included) and not invalid_handoffs and not unresolved_selectors
    blocked_reason = _blocked_reason(
        included=included,
        missing_handoffs=missing_handoffs,
        invalid_handoffs=invalid_handoffs,
        unresolved_selectors=unresolved_selectors,
    )
    return {
        "status": "ready" if ready else "blocked",
        "blocked_reason": blocked_reason,
        "expected_handoff_dir": str(expected_handoff_dir),
        "selected_session_count": len(included),
        "matching_handoff_count": len(included),
        "missing_handoff_count": len(missing_handoffs),
        "invalid_handoff_count": len(invalid_handoffs),
        "unresolved_session_selectors": unresolved_selectors,
        "missing_expected_handoffs": missing_handoffs[:20],
        "invalid_handoffs": invalid_handoffs[:20],
        "repair_guidance": _repair_guidance(
            blocked_reason=blocked_reason,
            expected_handoff_dir=expected_handoff_dir,
            missing_handoffs=missing_handoffs,
            invalid_handoffs=invalid_handoffs,
            unresolved_selectors=unresolved_selectors,
        ),
    }


def _blocked_reason(
    *,
    included: list[dict[str, Any]],
    missing_handoffs: list[dict[str, Any]],
    invalid_handoffs: list[dict[str, Any]],
    unresolved_selectors: list[str],
) -> str:
    if unresolved_selectors:
        return "unresolved_session_selector"
    if invalid_handoffs:
        return "invalid_handoff_json"
    if not included and missing_handoffs:
        return "missing_handoff_json"
    if not included:
        return "no_matching_handoffs"
    return ""


def _repair_guidance(
    *,
    blocked_reason: str,
    expected_handoff_dir: Path,
    missing_handoffs: list[dict[str, Any]],
    invalid_handoffs: list[dict[str, Any]],
    unresolved_selectors: list[str],
) -> list[str]:
    if not blocked_reason:
        return []
    guidance = [
        (
            "This command is derived-only; it will not read raw provider "
            "sessions or generate handoffs implicitly."
        ),
        f"Expected handoff JSON directory: {expected_handoff_dir}",
    ]
    if unresolved_selectors:
        guidance.append(
            "Check that each --session-id or sessions manifest entry exists "
            "in the derived mirror index."
        )
    if missing_handoffs:
        guidance.append(
            "Generate the missing handoff JSON artifacts before running the context pack again."
        )
        sample_ids = ", ".join(
            str(item.get("session_id") or "") for item in missing_handoffs[:5]
        )
        if sample_ids:
            guidance.append(f"Missing handoff session sample: {sample_ids}")
    if invalid_handoffs:
        guidance.append("Regenerate or remove invalid handoff JSON artifacts.")
    if blocked_reason == "no_matching_handoffs":
        guidance.append(
            "Relax filters or generate handoffs for sessions matching the selected scope."
        )
    return guidance


def _redaction_mode(included: list[dict[str, Any]]) -> str:
    if not included:
        return "none_selected"
    redacted_count = sum(1 for item in included if item.get("redacted") is True)
    if redacted_count == len(included):
        return "all_redacted"
    if redacted_count == 0:
        return "not_redacted"
    return "mixed"


def _manifest_source_hashes(included: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "scope": "derived_artifacts_only",
        "handoff_json_sha256_by_session": {
            str(item.get("session_id")): _string(
                _as_dict(item.get("source_hashes")).get("handoff_json_sha256")
            )
            for item in included
            if _string(_as_dict(item.get("source_hashes")).get("handoff_json_sha256"))
        },
        "metadata_json_sha256_by_session": {
            str(item.get("session_id")): _string(
                _as_dict(item.get("source_hashes")).get("metadata_json_sha256")
            )
            for item in included
            if _string(_as_dict(item.get("source_hashes")).get("metadata_json_sha256"))
        },
    }


def _unresolved_selectors(
    entries: list[MirrorEntry],
    options: ContextPackOptions,
) -> list[str]:
    if not options.session_ids:
        return []
    session_ids = [entry_session_id(entry) for entry in entries]
    unresolved: list[str] = []
    for selector in options.session_ids:
        if not any(_selector_matches(session_id, selector) for session_id in session_ids):
            unresolved.append(selector)
    return unresolved


def _manifest_limitations() -> list[str]:
    return [
        (
            "This manifest is historical advisory context only; repo-local "
            "Workstation sources remain authoritative."
        ),
        (
            "Raw provider transcripts, live sessions, credentials, auth, config, "
            "and runtime state are excluded."
        ),
        "Source hashes cover derived artifacts only.",
        "Session ranking is deterministic and local; it is not an LLM relevance judgment.",
    ]


def _session_limitations(
    *,
    payload: dict[str, Any],
    prompt_compliance: dict[str, Any],
    source_contract: dict[str, Any],
) -> list[str]:
    source = _as_dict(payload.get("source_availability"))
    limitations = [str(item) for item in _as_list(source.get("limitations")) if str(item)]
    if not bool(payload.get("redacted")):
        limitations.append(
            "Handoff was generated without redaction; downstream consumers "
            "should treat content according to local policy."
        )
    if prompt_compliance.get("status") != "pass":
        limitations.append("Restart prompt compliance did not pass.")
    if source_contract.get("status") != "pass":
        limitations.append("Source availability contract did not pass.")
    limitations.append(
        "Raw transcript and transcript excerpt are excluded from this context pack item."
    )
    return _dedupe(limitations)


def _redaction_status(entry: MirrorEntry, payload: dict[str, Any]) -> dict[str, Any]:
    report = _as_dict(entry.get("redaction_report"))
    return {
        "redacted": bool(payload.get("redacted") or entry.get("redacted")),
        "report_available": bool(report),
        "best_effort": bool(report.get("best_effort")) if report else True,
        "total_replacements": int(report.get("total_replacements") or 0) if report else 0,
        "placeholder_totals": _as_dict(report.get("placeholder_totals")) if report else {},
        "note": _string(report.get("note")) if report else "",
    }


def _source_hashes(
    *,
    handoff_json_path: Path,
    handoff_markdown_path: Path,
    metadata_path: Path,
) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for key, path in (
        ("handoff_json_sha256", handoff_json_path),
        ("handoff_markdown_sha256", handoff_markdown_path),
        ("metadata_json_sha256", metadata_path),
    ):
        digest = _sha256_file(path)
        if digest:
            hashes[key] = digest
    return hashes


def _query_score(payload: dict[str, Any], entry: MirrorEntry, query: str) -> int:
    normalized_query = " ".join(query.lower().split())
    if not normalized_query:
        return 0
    haystack = _search_text(payload, entry)
    return haystack.count(normalized_query)


def _search_text(payload: dict[str, Any], entry: MirrorEntry) -> str:
    searchable = {
        "title": payload.get("title") or entry_title(entry),
        "session": payload.get("session"),
        "continuation_brief": payload.get("continuation_brief"),
        "resolved_state": payload.get("resolved_state"),
        "current_state": payload.get("current_state"),
        "decisions_and_invariants": payload.get("decisions_and_invariants"),
        "changed_artifacts": payload.get("changed_artifacts"),
        "open_loops": payload.get("open_loops"),
        "roadmap_evidence": payload.get("roadmap_evidence"),
        "repo_evidence": payload.get("repo_evidence"),
    }
    return " ".join(json.dumps(searchable, ensure_ascii=False, sort_keys=True).lower().split())


def _unique_recent_entries(entries: list[MirrorEntry]) -> list[MirrorEntry]:
    unique: dict[str, MirrorEntry] = {}
    for entry in sort_entries(entries):
        unique.setdefault(entry_session_id(entry), entry)
    return list(unique.values())


def _skipped_session(
    entry: MirrorEntry,
    *,
    reason: str,
    path: Path,
    error: str = "",
) -> dict[str, Any]:
    item = {
        "session_id": entry_session_id(entry),
        "title": entry_title(entry),
        "reason": reason,
        "path": str(path),
    }
    if error:
        item["error"] = error
    return item


def _session_repo_root(payload: dict[str, Any], entry: MirrorEntry) -> str:
    return _string(_as_dict(payload.get("artifacts")).get("repo_root")) or _string(entry.get("cwd"))


def _session_timestamp(payload: dict[str, Any], entry: MirrorEntry) -> str:
    for value in (
        payload.get("updated_at"),
        entry.get("updated_at"),
        payload.get("session_timestamp"),
        entry.get("session_timestamp"),
        payload.get("generated_at"),
        entry.get("exported_at"),
    ):
        if value:
            return str(value)
    return ""


def _timestamp_at_or_after(timestamp: str, boundary: str) -> bool:
    parsed = _parse_timestamp(timestamp)
    parsed_boundary = _parse_timestamp(boundary)
    if parsed is None or parsed_boundary is None:
        return timestamp >= boundary
    return parsed >= parsed_boundary


def _timestamp_at_or_before(timestamp: str, boundary: str) -> bool:
    parsed = _parse_timestamp(timestamp)
    parsed_boundary = _parse_timestamp(boundary)
    if parsed is None or parsed_boundary is None:
        return timestamp <= boundary
    return parsed <= parsed_boundary


def _timestamp_score(timestamp: str) -> float:
    parsed = _parse_timestamp(timestamp)
    if parsed is None:
        return 0.0
    return parsed.timestamp()


def _parse_timestamp(value: str) -> datetime | None:
    text = value.strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _entry_or_artifact_relpath(
    entry: MirrorEntry,
    artifacts: dict[str, Any],
    kind: str,
) -> str:
    if kind == "metadata":
        return _string(artifacts.get("metadata_relpath")) or _string(entry.get("metadata_relpath"))
    return ""


def _derived_path(out_dir: Path, relpath: str) -> Path:
    if not relpath:
        return Path()
    path = Path(relpath)
    if path.is_absolute():
        return path
    return out_dir / path


def _relative_to(path: Path, root: Path) -> str:
    if not path:
        return ""
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _sha256_file(path: Path) -> str:
    if not path or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _limited_list(value: Any, *, limit: int) -> dict[str, Any]:
    items = _as_list(value)
    safe_limit = max(0, limit)
    return {
        "items": items[:safe_limit],
        "count": len(items),
        "limit": safe_limit,
        "truncated": len(items) > safe_limit,
    }


def _only_keys(value: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: value.get(key, "") for key in keys}


def _restart_prompt_text(payload: dict[str, Any]) -> str:
    return _string(_as_dict(payload.get("restart_prompt")).get("text")).strip()


def _selector_matches(session_id: str, selector: str) -> bool:
    normalized = selector.strip()
    return bool(normalized) and session_id.startswith(normalized)


def _normalized_path_filter(path: str) -> str:
    if not path:
        return ""
    return str(Path(path).expanduser())


def _status_counts(values: Any) -> dict[str, int]:
    counts = {status: 0 for status in SUMMARY_STATUS_VALUES}
    for value in values:
        status = str(value or "error")
        counts[status if status in counts else "error"] += 1
    return counts


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            result.append(item)
            seen.add(item)
    return result


def _iso_now() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string(value: Any) -> str:
    return value if isinstance(value, str) else ""
