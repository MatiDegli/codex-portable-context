"""Source session loading and provider source availability."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any

from codex_portable_context.providers import get_provider_adapter

from ..parsing import ParsedSession
from .constants import PROVIDER_CAPABILITY_KEYS, SECTION_SOURCE_VALUES, SOURCE_MODE_VALUES
from .utils import _string


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
        "repo_evidence": "derived_mirror",
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
