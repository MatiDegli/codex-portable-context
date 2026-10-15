"""Roadmap and repository evidence discovery (attribution only)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..parsing import ParsedSession
from ..redaction import RedactionContext, redact_text
from .constants import (
    REPO_EVIDENCE_EXCLUDED_PARTS,
    REPO_EVIDENCE_GLOB_PATTERNS,
    REPO_EVIDENCE_KNOWN_RELATIVE_PATHS,
    REPO_EVIDENCE_PROMPT_THRESHOLD,
    REPO_EVIDENCE_STORE_THRESHOLD,
    REPO_EVIDENCE_SYNTHESIS_THRESHOLD,
    ROADMAP_GLOB_PATTERNS,
    ROADMAP_KNOWN_RELATIVE_PATHS,
    ROADMAP_SIGNAL_MARKERS,
)
from .utils import _as_list, _excerpt_text, _string


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


def _build_repo_evidence(
    *,
    repo_state: dict[str, Any],
    roadmap_evidence: dict[str, Any],
    continuity_freshness: dict[str, str],
    open_loops: dict[str, str],
    resolved_state: dict[str, str],
    redacted: bool,
    context: RedactionContext,
) -> dict[str, Any]:
    repo_root = _string(repo_state.get("repo_root"))
    if not repo_root:
        return _empty_repo_evidence(
            status="unavailable",
            summary="Repo root was unavailable, so repo evidence was not scanned.",
        )

    root = Path(repo_root).expanduser()
    if not root.is_dir():
        return _empty_repo_evidence(
            status="unavailable",
            summary="Repo root does not exist locally, so repo evidence was not scanned.",
        )

    sources = _repo_evidence_sources(root=root, redacted=redacted, context=context)
    if not sources:
        return _empty_repo_evidence(
            status="none",
            summary="No conservative repo evidence sources passed the storage threshold.",
        )

    inclusion_reason = _repo_evidence_inclusion_reason(
        repo_state=repo_state,
        roadmap_evidence=roadmap_evidence,
        continuity_freshness=continuity_freshness,
        open_loops=open_loops,
        resolved_state=resolved_state,
    )
    prompt_paths = _repo_evidence_prompt_paths(sources, inclusion_reason=inclusion_reason)
    prompt_path_set = set(prompt_paths)
    marked_sources = [
        {
            **source,
            "include_in_restart_prompt": source["path"] in prompt_path_set,
        }
        for source in sources
    ]
    max_confidence = max(float(source.get("confidence") or 0.0) for source in sources)
    return {
        "status": "found",
        "summary": (
            f"Found {len(sources)} conservative repo evidence source(s). "
            "This slice stores attributed evidence and keeps synthesis disabled."
        ),
        "sources": marked_sources,
        "recommended_inspection_order": [source["path"] for source in marked_sources[:8]],
        "prompt_sources": prompt_paths,
        "inclusion_reason": inclusion_reason,
        "max_confidence": round(max_confidence, 2),
        "store_threshold": REPO_EVIDENCE_STORE_THRESHOLD,
        "prompt_threshold": REPO_EVIDENCE_PROMPT_THRESHOLD,
        "synthesis_threshold": REPO_EVIDENCE_SYNTHESIS_THRESHOLD,
        "include_in_restart_prompt": bool(prompt_paths),
        "used_for_synthesis": False,
    }


def _empty_repo_evidence(*, status: str, summary: str) -> dict[str, Any]:
    return {
        "status": status,
        "summary": summary,
        "sources": [],
        "recommended_inspection_order": [],
        "prompt_sources": [],
        "inclusion_reason": "none",
        "max_confidence": 0.0,
        "store_threshold": REPO_EVIDENCE_STORE_THRESHOLD,
        "prompt_threshold": REPO_EVIDENCE_PROMPT_THRESHOLD,
        "synthesis_threshold": REPO_EVIDENCE_SYNTHESIS_THRESHOLD,
        "include_in_restart_prompt": False,
        "used_for_synthesis": False,
    }


def _repo_evidence_sources(
    *,
    root: Path,
    redacted: bool,
    context: RedactionContext,
) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for path in _candidate_repo_evidence_paths(root):
        source = _repo_evidence_source_from_path(path, root=root)
        if not source:
            continue
        if float(source.get("confidence") or 0.0) < REPO_EVIDENCE_STORE_THRESHOLD:
            continue
        if redacted:
            source = {
                **source,
                "path": redact_text(source["path"], context).text,
                "excerpt": redact_text(source["excerpt"], context).text,
            }
        sources.append(source)
        if len(sources) >= 12:
            break
    return sources


def _candidate_repo_evidence_paths(root: Path) -> list[Path]:
    candidates: list[Path] = []

    def add(path: Path) -> None:
        if (
            path.is_file()
            and _is_safe_repo_evidence_path(path, root=root)
            and path not in candidates
        ):
            candidates.append(path)

    for relpath in REPO_EVIDENCE_KNOWN_RELATIVE_PATHS:
        add(root / relpath)

    for pattern in REPO_EVIDENCE_GLOB_PATTERNS:
        for path in sorted(root.glob(pattern)):
            add(path)

    return candidates


def _is_safe_repo_evidence_path(path: Path, *, root: Path) -> bool:
    try:
        relpath = path.relative_to(root)
    except ValueError:
        return False
    parts = set(relpath.parts)
    if parts & REPO_EVIDENCE_EXCLUDED_PARTS:
        return False
    rendered = relpath.as_posix()
    lowered = rendered.lower()
    if lowered.endswith((".env", ".vsix")) or ".env." in lowered:
        return False
    if any(part.startswith(".") and part not in {".github"} for part in relpath.parts):
        return False
    try:
        if path.stat().st_size > 180_000:
            return False
    except OSError:
        return False
    return True


def _repo_evidence_source_from_path(path: Path, *, root: Path) -> dict[str, Any]:
    try:
        relpath = path.relative_to(root).as_posix()
    except ValueError:
        return {}

    try:
        text = path.read_text(encoding="utf-8", errors="replace")[:120_000]
    except OSError:
        return {}

    if relpath == "package.json":
        return _package_json_repo_evidence(relpath=relpath, text=text)
    if relpath == "pyproject.toml":
        return _pyproject_repo_evidence(relpath=relpath, text=text)
    if relpath.startswith(".github/workflows/"):
        return _workflow_repo_evidence(relpath=relpath, text=text)

    kind = _repo_evidence_kind(relpath)
    signals = _repo_evidence_signals(text, relpath)
    excerpt = _repo_evidence_excerpt(text, kind=kind)
    confidence = _repo_evidence_confidence(kind=kind, signals=signals, excerpt=excerpt)
    if not excerpt or not signals:
        return {}
    return {
        "path": relpath,
        "kind": kind,
        "reason": _repo_evidence_reason(kind),
        "confidence": confidence,
        "signals": signals[:6],
        "excerpt": excerpt,
    }


def _repo_evidence_kind(path: str) -> str:
    lowered = path.lower()
    if lowered in {"agents.md", "claude.md"}:
        return "agent_instructions"
    if lowered == "conventions.md":
        return "conventions"
    if "next" in lowered and "step" in lowered:
        return "next_steps"
    if "roadmap" in lowered:
        return "roadmap"
    if "status" in lowered:
        return "status"
    if lowered == "readme.md":
        return "project_overview"
    return "repo_doc"


def _repo_evidence_reason(kind: str) -> str:
    return {
        "agent_instructions": "canonical_agent_instructions",
        "conventions": "canonical_repo_conventions",
        "next_steps": "canonical_next_steps",
        "roadmap": "repo_roadmap",
        "status": "repo_status",
        "project_overview": "repo_readme",
        "workflow_validation": "ci_validation_surface",
        "package_scripts": "package_validation_surface",
        "python_project_config": "python_project_config",
    }.get(kind, "repo_doc")


def _repo_evidence_signals(text: str, path: str) -> list[str]:
    lowered = f"{path}\n{text}".lower()
    markers = (
        "source of truth",
        "current priority",
        "next step",
        "next steps",
        "roadmap",
        "status",
        "validation",
        "test",
        "pytest",
        "ruff",
        "mypy",
        "npm test",
        "pnpm test",
        "vitest",
        "conventions",
        "must",
        "must not",
        "do not",
        "debe",
        "no debe",
        "architecture",
        "workflow",
        "ci",
    )
    return [marker for marker in markers if marker in lowered]


def _repo_evidence_excerpt(text: str, *, kind: str) -> str:
    markers = (
        "source of truth",
        "current priority",
        "next step",
        "next steps",
        "roadmap",
        "status",
        "validation",
        "pytest",
        "ruff",
        "mypy",
        "must ",
        "must not",
        "do not",
        "debe",
        "no debe",
    )
    fallback = ""
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        line = stripped.strip("-* ")
        if not line or line in {"---", "```"}:
            continue
        if _is_generic_roadmap_heading(line):
            continue
        if not fallback and kind in {"project_overview", "repo_doc"}:
            fallback = line
        lowered = line.lower()
        if any(marker in lowered for marker in markers):
            return _excerpt_text(line, limit=220)
    return _excerpt_text(fallback, limit=220) if fallback else ""


def _repo_evidence_confidence(*, kind: str, signals: list[str], excerpt: str) -> float:
    if not signals or not excerpt:
        return 0.0
    if kind in {"next_steps", "roadmap", "status"}:
        return 0.85
    if kind in {"agent_instructions", "conventions"}:
        return 0.80
    if kind in {"workflow_validation", "package_scripts"}:
        return 0.85
    if kind == "python_project_config":
        return 0.70
    if kind == "project_overview":
        return 0.60 if len(signals) < 2 else 0.70
    return 0.55


def _workflow_repo_evidence(*, relpath: str, text: str) -> dict[str, Any]:
    run_lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("- run:"):
            command = line.split("- run:", 1)[1].strip()
        elif line.startswith("run:"):
            command = line.split("run:", 1)[1].strip()
        else:
            continue
        if _looks_like_validation_command(command):
            run_lines.append(command)
    if not run_lines:
        return {}
    excerpt = "; ".join(run_lines[:3])
    return {
        "path": relpath,
        "kind": "workflow_validation",
        "reason": _repo_evidence_reason("workflow_validation"),
        "confidence": 0.85,
        "signals": ["workflow", "validation"],
        "excerpt": _excerpt_text(excerpt, limit=220),
    }


def _package_json_repo_evidence(*, relpath: str, text: str) -> dict[str, Any]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    scripts = payload.get("scripts")
    if not isinstance(scripts, dict):
        return {}
    interesting: list[str] = []
    for name, command in scripts.items():
        if not isinstance(name, str) or not isinstance(command, str):
            continue
        if _is_validation_script_name(name) or _looks_like_validation_command(command):
            interesting.append(f"{name}: {command}")
    if not interesting:
        return {}
    return {
        "path": relpath,
        "kind": "package_scripts",
        "reason": _repo_evidence_reason("package_scripts"),
        "confidence": 0.85,
        "signals": ["package scripts", "validation"],
        "excerpt": _excerpt_text("; ".join(interesting[:4]), limit=220),
    }


def _pyproject_repo_evidence(*, relpath: str, text: str) -> dict[str, Any]:
    interesting: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        lowered = line.lower()
        if lowered.startswith(("[tool.pytest", "[tool.ruff", "[tool.mypy", "[project.scripts]")):
            interesting.append(line)
    if not interesting:
        return {}
    return {
        "path": relpath,
        "kind": "python_project_config",
        "reason": _repo_evidence_reason("python_project_config"),
        "confidence": 0.70,
        "signals": ["python project config", "validation"],
        "excerpt": _excerpt_text("; ".join(interesting[:4]), limit=220),
    }


def _is_validation_script_name(name: str) -> bool:
    lowered = name.lower()
    return any(marker in lowered for marker in ("test", "lint", "typecheck", "validate", "check"))


def _looks_like_validation_command(command: str) -> bool:
    lowered = command.lower()
    return any(
        marker in lowered
        for marker in (
            "pytest",
            "ruff",
            "mypy",
            "npm test",
            "pnpm test",
            "yarn test",
            "vitest",
            "eslint",
            "tsc",
            "cargo test",
            "go test",
        )
    )


def _repo_evidence_inclusion_reason(
    *,
    repo_state: dict[str, Any],
    roadmap_evidence: dict[str, Any],
    continuity_freshness: dict[str, str],
    open_loops: dict[str, str],
    resolved_state: dict[str, str],
) -> str:
    freshness_status = _string(continuity_freshness.get("status"))
    if freshness_status.startswith("stale_"):
        return "freshness_warning"
    if roadmap_evidence.get("include_in_restart_prompt"):
        return "roadmap_context_needed"
    if _string(repo_state.get("repo_root_source")) == "inferred_from_artifact_paths":
        return "inferred_repo_context"
    if _string(open_loops.get("pending_validation")) != "none":
        return "validation_context_needed"
    if _is_missing_validation_text(_string(resolved_state.get("validation_summary"))):
        return "validation_context_needed"
    return "none"


def _repo_evidence_prompt_paths(
    sources: list[dict[str, Any]],
    *,
    inclusion_reason: str,
) -> list[str]:
    if inclusion_reason == "none":
        return []
    allowed_kinds = _repo_evidence_prompt_allowed_kinds(inclusion_reason)
    paths: list[str] = []
    for source in sources:
        if len(paths) >= 5:
            break
        if float(source.get("confidence") or 0.0) < REPO_EVIDENCE_PROMPT_THRESHOLD:
            continue
        if source.get("kind") not in allowed_kinds:
            continue
        path = _string(source.get("path"))
        if path:
            paths.append(path)
    return paths


def _repo_evidence_prompt_allowed_kinds(inclusion_reason: str) -> set[str]:
    if inclusion_reason in {"freshness_warning", "roadmap_context_needed"}:
        return {"next_steps", "roadmap", "status"}
    if inclusion_reason == "validation_context_needed":
        return {"agent_instructions", "conventions", "workflow_validation", "package_scripts"}
    if inclusion_reason == "inferred_repo_context":
        return {"agent_instructions", "conventions", "next_steps", "roadmap", "status"}
    return set()


def _is_missing_validation_text(text: str) -> bool:
    lowered = text.lower().strip()
    return not lowered or lowered.startswith("no recent validation signal")
