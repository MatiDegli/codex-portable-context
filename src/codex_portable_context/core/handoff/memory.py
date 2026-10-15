"""Decisions, invariants and outcome memory extracted from the transcript."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..parsing import ParsedSession
from ..redaction import RedactionContext, redact_text
from .artifacts import _strip_embedded_restart_prompt_payload
from .constants import RECENT_ACTION_LOOKBACK
from .state import _normalize_for_matching
from .utils import _excerpt_text, _string


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
    request_resolution_status = _string(resolved_state.get("request_resolution_status"))
    request_is_resolved = request_resolution_status in {
        "answered",
        "handled_with_changes",
        "completed",
    }

    sources = [
        ("continuation_brief", _string(continuation_brief.get("what_we_were_doing"))),
        ("resolved_state", _string(resolved_state.get("contextual_user_request"))),
        ("changed_artifacts", _string(changed_artifacts.get("summary"))),
    ]
    if parsed:
        sources.extend(_structural_memory_sources(parsed))
        sources.extend(_review_memory_sources(parsed))
        sources.extend(_implementation_outcome_sources(parsed))
        sources.extend(_answer_outcome_sources(parsed))
        sources.extend(
            (f"recent_window_{block.kind}", block.text)
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
                if (
                    source in {"continuation_brief", "resolved_state", "recent_window_user"}
                    and request_is_resolved
                ):
                    continue
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


def _answer_outcome_sources(parsed: ParsedSession) -> list[tuple[str, str]]:
    sources: list[tuple[str, str]] = []
    for block in parsed.conversation_entries[-RECENT_ACTION_LOOKBACK:]:
        if block.kind != "assistant":
            continue
        candidates = _answer_outcome_candidates_from_text(block.text)
        if candidates:
            sources.append(
                (
                    "answer_outcome",
                    "\n".join(f"- {candidate}" for candidate in candidates),
                )
            )
    return sources


def _answer_outcome_candidates_from_text(text: str) -> list[str]:
    if not _has_answer_outcome_signal(text):
        return []

    candidates: list[str] = []
    active_label = ""
    in_fence = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not line:
            continue

        heading = _answer_outcome_heading(line)
        if heading:
            active_label = heading
            inline_candidate = _answer_outcome_inline_heading_candidate(line, heading)
            if inline_candidate:
                candidates.append(inline_candidate)
            continue

        if line.startswith("#"):
            active_label = ""
            continue

        first_line_candidate = _answer_outcome_first_line_candidate(line)
        if first_line_candidate:
            candidates.append(first_line_candidate)
            continue

        list_item = _structural_list_item(line)
        if not list_item:
            continue
        candidate = _answer_outcome_candidate(active_label, list_item)
        if candidate:
            candidates.append(candidate)

    return candidates[:32]


def _has_answer_outcome_signal(text: str) -> bool:
    lowered = text.lower()
    if (
        "continue from a local extractive handoff" in lowered
        or "first response contract" in lowered
    ):
        return False
    markers = (
        "mi recomendación",
        "mi recomendacion",
        "recommendation",
        "recommended",
        "conclusión",
        "conclusion",
        "entonces:",
        "en resumen",
        "bottom line",
        "obligatorio:",
        "recomendable:",
        "conviene",
        "yo lo dejaría",
        "yo lo dejaria",
        "está bien para hacerlo público",
        "esta bien para hacerlo publico",
        "bien para hacerlo público",
        "bien para hacerlo publico",
        "no veo secretos",
        "lo único sensible",
        "lo unico sensible",
        "pii",
        "noreply",
    )
    return any(marker in lowered for marker in markers)


def _answer_outcome_heading(line: str) -> str:
    stripped = line.strip()
    inline_prefix = re.match(r"^\**\s*([^:*]+):\**\s+.+$", stripped)
    if inline_prefix:
        prefix = inline_prefix.group(1).strip().lower()
        if prefix in {
            "mi recomendación",
            "mi recomendacion",
            "recommendation",
            "recommended next step",
            "conclusión",
            "conclusion",
            "en resumen",
            "bottom line",
            "entonces",
        }:
            if "recomend" in prefix or "recommend" in prefix:
                return "Recommendation"
            return "Conclusion"
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
        "mi recomendación": "Recommendation",
        "mi recomendacion": "Recommendation",
        "recommendation": "Recommendation",
        "recommended next step": "Recommendation",
        "conclusión": "Conclusion",
        "conclusion": "Conclusion",
        "en resumen": "Conclusion",
        "bottom line": "Conclusion",
        "entonces": "Conclusion",
    }
    return accepted.get(lowered, "")


def _answer_outcome_inline_heading_candidate(line: str, heading: str) -> str:
    cleaned = line.strip()
    if not cleaned or cleaned.endswith(":"):
        return ""
    match = re.match(r"^\**\s*[^:*]+:\**\s*(.+)$", cleaned)
    if not match:
        return ""
    candidate = match.group(1).strip()
    return _answer_outcome_candidate(heading, candidate)


def _answer_outcome_first_line_candidate(line: str) -> str:
    cleaned = line.strip()
    if _is_memory_bullet_line(cleaned):
        return ""
    lowered = cleaned.lower()
    if not (
        lowered.startswith(("sí,", "si,", "no ", "no,", "de hecho", "entonces"))
        or lowered.startswith(("lo único sensible", "lo unico sensible"))
        or lowered.startswith(("mi recomendación:", "mi recomendacion:", "recommendation:"))
        or " está bien para hacerlo público" in lowered
        or " esta bien para hacerlo publico" in lowered
    ):
        return ""
    if not _has_answer_memory_signal(cleaned):
        return ""
    return _excerpt_text(f"Conclusion: {cleaned}", limit=240)


def _answer_outcome_candidate(label: str, text: str) -> str:
    cleaned = text.strip()
    if not cleaned or _looks_like_validation_line(cleaned):
        return ""
    if cleaned.startswith("[") and "](" in cleaned:
        return ""
    if _looks_like_path_only_item(cleaned):
        return ""
    if not _has_answer_memory_signal(cleaned):
        return ""
    prefix = label or "Conclusion"
    return _excerpt_text(f"{prefix}: {cleaned}", limit=240)


def _has_answer_memory_signal(text: str) -> bool:
    lowered = text.lower()
    markers = (
        "conviene",
        "recomendable",
        "obligatorio",
        "no estrictamente",
        "no es obligatorio",
        "probablemente funcione",
        "claridad de tipo",
        "pid",
        "centinela",
        "warning",
        "warnings",
        "público",
        "publico",
        "secretos",
        "sensible",
        "pii",
        "metadata de los commits",
        "email real",
        "noreply",
        "reescribir",
        "pushear",
    )
    return any(marker in lowered for marker in markers)


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
    in_fence = False

    def flush_paragraph() -> None:
        if paragraph:
            segments.append(" ".join(paragraph))
            paragraph.clear()

    for raw_line in text.strip().splitlines():
        line = raw_line.strip()
        if line.startswith("```"):
            flush_paragraph()
            in_fence = not in_fence
            continue
        if in_fence:
            continue
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
        "conclusion",
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
        "no estrictamente",
        "obligatorio",
        "recomendable",
        "claridad de tipo",
        "centinela",
        "público",
        "publico",
        "secretos",
        "sensible",
        "pii",
        "metadata de los commits",
        "email real",
        "noreply",
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
        "conclusion",
        "resolved during review",
        "implementation outcome",
        "behavior now",
        "what changed",
        "público",
        "publico",
        "no estrictamente",
        "recomendable",
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
        "centinela",
        "claridad de tipo",
        "secretos",
        "sensible",
        "pii",
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
        "email real",
        "noreply",
        "reescribir",
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
