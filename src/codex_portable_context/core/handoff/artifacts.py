"""Changed-artifact extraction and normalization."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..parsing import ParsedSession
from ..redaction import RedactionContext, redact_text
from .constants import RECENT_ACTION_LOOKBACK
from .utils import _as_dict, _as_list, _parse_tool_call_json, _string


def _build_changed_artifacts(
    *,
    parsed: ParsedSession | None,
    resolved_state: dict[str, str],
    recent_window: list[dict[str, Any]],
    repo_state: dict[str, Any],
    redacted: bool,
    context: RedactionContext,
) -> dict[str, Any]:
    changed_paths: list[dict[str, str]] = []
    key_paths: list[dict[str, str]] = []
    repo_root = _string(repo_state.get("repo_root"))

    if parsed:
        for block in parsed.conversation_entries[-RECENT_ACTION_LOOKBACK:]:
            if block.kind == "tool_output" and "Updated the following files:" in block.text:
                for path in _updated_files_from_tool_output(block.text):
                    resolved_path = _resolve_artifact_path(
                        path,
                        repo_root=repo_root,
                    )
                    _append_artifact(
                        changed_paths,
                        path=resolved_path,
                        source="tool_output_updated_files",
                        status="changed",
                        note="Reported by recent tool output.",
                        redacted=redacted,
                        context=context,
                    )

    for item in _as_list(repo_state.get("repo_dirty_paths")):
        artifact = _as_dict(item)
        _append_artifact(
            changed_paths,
            path=_string(artifact.get("path")),
            source="git_status",
            status=_string(artifact.get("status")) or "dirty",
            note="Repo has this path in git status.",
            redacted=redacted,
            context=context,
        )

    text_sources = [
        _string(resolved_state.get("latest_user_request")),
        _string(resolved_state.get("contextual_user_request")),
        _string(resolved_state.get("resolution_summary")),
    ]
    text_sources.extend(
        _string(item.get("text")) for item in recent_window if isinstance(item, dict)
    )
    for text in text_sources:
        for path in _path_mentions_from_text(text):
            resolved_path = _resolve_artifact_path(path, repo_root=repo_root)
            _append_artifact(
                key_paths,
                path=resolved_path,
                source="recent_text_path_mention",
                status="referenced",
                note="Mentioned in recent request, response, or summary.",
                redacted=redacted,
                context=context,
            )

    recommended = _recommended_inspection_order(changed_paths, key_paths)
    summary = _changed_artifacts_summary(changed_paths, key_paths, recommended)
    return {
        "summary": summary,
        "changed_paths": changed_paths[:20],
        "key_paths": key_paths[:20],
        "recommended_inspection_order": recommended[:10],
    }


def _append_artifact(
    target: list[dict[str, str]],
    *,
    path: str,
    source: str,
    status: str,
    note: str,
    redacted: bool,
    context: RedactionContext,
) -> None:
    normalized = _normalize_artifact_path(path)
    if not normalized or _artifact_path_seen(target, normalized):
        return
    if redacted:
        normalized = redact_text(normalized, context).text
        note = redact_text(note, context).text
    target.append(
        {
            "path": normalized,
            "source": source,
            "status": status,
            "note": note,
        }
    )


def _artifact_path_seen(items: list[dict[str, str]], path: str) -> bool:
    return any(item.get("path") == path for item in items)


def _path_mentions_from_text(text: str) -> list[str]:
    text = _strip_embedded_restart_prompt_payload(text)
    paths: list[str] = []
    for match in re.finditer(r"\[[^\]]+\]\(([^)]+)\)", text):
        paths.append(match.group(1))
    for match in re.finditer(r"`([^`]*(?:/|\\)[^`]*)`", text):
        paths.append(match.group(1))
    for match in re.finditer(
        r"(?<![\w.-])(?:\.{0,2}/|/)[^\s)\],;:]+(?:\.[A-Za-z0-9_]+)(?::\d+)?",
        text,
    ):
        paths.append(match.group(0))
    return [_normalize_artifact_path(path) for path in paths if _normalize_artifact_path(path)]


def _normalize_artifact_path(path: str) -> str:
    cleaned = path.strip().strip("\"'")
    if "](" in cleaned:
        cleaned = cleaned.rsplit("](", maxsplit=1)[-1]
        cleaned = cleaned.split(")", maxsplit=1)[0]
    if cleaned.startswith("<") and cleaned.endswith(">"):
        cleaned = cleaned[1:-1].strip()
    cleaned = cleaned.replace("\\", "/")
    cleaned = re.sub(r"^file://", "", cleaned)
    cleaned = re.sub(r":\d+(?::\d+)?$", "", cleaned)
    cleaned = cleaned.rstrip(".,;)")
    if cleaned in {"/", "./", "../"}:
        return ""
    if _is_noisy_artifact_path(cleaned):
        return ""
    if not cleaned or cleaned.startswith(("http://", "https://")):
        return ""
    if _looks_like_shell_command_path(cleaned):
        return ""
    if re.search(r"\s+[/\\]\s+", cleaned):
        return ""
    if "\n" in cleaned or len(cleaned) > 260:
        return ""
    if re.search(r"\s--?[A-Za-z0-9][\w-]*(?:\s|=)", cleaned):
        return ""
    if "/" not in cleaned and "." not in Path(cleaned).name:
        return ""
    return cleaned


def _strip_embedded_restart_prompt_payload(text: str) -> str:
    marker_index = text.lower().find("continue from a local extractive handoff")
    if marker_index < 0:
        return text
    return text[:marker_index].strip()


def _resolve_artifact_path(path: str, *, repo_root: str) -> str:
    normalized = _normalize_artifact_path(path)
    if not normalized:
        return normalized
    repo_relative = _repo_relative_artifact_path(normalized, repo_root=repo_root)
    if repo_relative:
        return repo_relative
    if _is_extensionless_relative_nonexistent_path(normalized, repo_root=repo_root):
        return ""
    if "/" in normalized or "\\" in normalized:
        return normalized
    if not repo_root or not Path(normalized).suffix:
        return normalized

    root = Path(repo_root).expanduser()
    if not root.is_dir():
        return normalized

    matches = _repo_filename_matches(root, normalized)
    if len(matches) != 1:
        return normalized
    best_match = matches[0]
    try:
        return best_match.relative_to(root).as_posix()
    except ValueError:
        return best_match.as_posix()


def _is_extensionless_relative_nonexistent_path(path: str, *, repo_root: str) -> bool:
    if not repo_root:
        return False
    cleaned = path.rstrip("/")
    if not cleaned or Path(cleaned).is_absolute():
        return False
    if "/" not in cleaned and "\\" not in cleaned:
        return False
    if Path(cleaned).suffix:
        return False

    root = Path(repo_root).expanduser()
    if not root.is_dir():
        return False
    return not (root / cleaned).exists()


def _repo_filename_matches(root: Path, filename: str) -> list[Path]:
    ignored_dirs = {
        ".agent-bridge",
        ".codex",
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "node_modules",
        "out",
    }
    matches: list[Path] = []
    for candidate in root.rglob(filename):
        if any(part in ignored_dirs for part in candidate.parts):
            continue
        if candidate.is_file():
            matches.append(candidate)
        if len(matches) >= 25:
            break
    return matches


def _repo_relative_artifact_path(path: str, *, repo_root: str) -> str:
    if not repo_root:
        return ""
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        return ""
    root = Path(repo_root).expanduser()
    try:
        relative = candidate.resolve(strict=False).relative_to(root.resolve(strict=False))
    except (OSError, ValueError):
        return ""
    rendered = relative.as_posix()
    return "" if rendered == "." else rendered


def _is_noisy_artifact_path(path: str) -> bool:
    normalized = path.strip().replace("\\", "/")
    if re.fullmatch(r"\d+/\d+", normalized):
        return True
    if "/.cache/starship/" in normalized or normalized.startswith(".cache/starship/"):
        return True
    if "/.cache/" in normalized and re.search(r"/session_\d+\.log$", normalized):
        return True
    return False


def _looks_like_shell_command_path(path: str) -> bool:
    first_token = path.strip().split(maxsplit=1)[0] if path.strip() else ""
    return first_token in {
        "bash",
        "sh",
        "python",
        "python3",
        "uv",
        "pytest",
        "ruff",
        "mypy",
        "workstation",
        "codex-session-handoff",
        "codex-session-mirror",
    }


def _recommended_inspection_order(
    changed_paths: list[dict[str, str]],
    key_paths: list[dict[str, str]],
) -> list[str]:
    ordered: list[str] = []
    qualified_basenames = _qualified_artifact_basenames([*key_paths, *changed_paths])
    for item in [*key_paths, *changed_paths]:
        path = item.get("path", "")
        if not path or path in ordered:
            continue
        if not _is_recommended_artifact_path(path):
            continue
        if _is_bare_artifact_path(path) and Path(path).name in qualified_basenames:
            continue
        ordered.append(path)
    return ordered


def _qualified_artifact_basenames(items: list[dict[str, str]]) -> set[str]:
    basenames: set[str] = set()
    for item in items:
        path = item.get("path", "")
        if "/" in path.replace("\\", "/"):
            name = Path(path.replace("\\", "/")).name
            if name:
                basenames.add(name)
    return basenames


def _is_bare_artifact_path(path: str) -> bool:
    normalized = path.strip().replace("\\", "/")
    return bool(normalized) and "/" not in normalized and "." in Path(normalized).name


def _is_recommended_artifact_path(path: str) -> bool:
    normalized = path.strip().replace("\\", "/")
    if not normalized:
        return False
    if _is_noisy_artifact_path(normalized):
        return False
    if normalized in {".codex", ".agent-bridge", ".agent-bridge/", "workflow", "workflow/"}:
        return False
    if normalized.startswith((".codex/", ".agent-bridge/", "workflow/")):
        return False
    if normalized == "__init__.py":
        return False
    if normalized.endswith(".env") or "/.env" in normalized:
        return False
    return True


def _changed_artifacts_summary(
    changed_paths: list[dict[str, str]],
    key_paths: list[dict[str, str]],
    recommended: list[str],
) -> str:
    if not changed_paths and not key_paths:
        return "No concrete artifact paths were extracted from the recent handoff context."
    return (
        f"Extracted {len(changed_paths)} changed path(s), {len(key_paths)} key "
        f"path(s), and {len(recommended)} recommended inspection target(s)."
    )


def _updated_files_from_tool_output(text: str) -> list[str]:
    payload = _parse_tool_call_json(text)
    output_text = _string(payload.get("output")) if payload else ""
    haystack = output_text or text

    files: list[str] = []
    capture = False
    for raw_line in haystack.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line in {
            "Updated the following files:",
            "Success. Updated the following files:",
        }:
            capture = True
            continue
        if not capture:
            continue
        if line.startswith("{") or line.startswith('"metadata"'):
            break
        normalized = re.sub(r"^[A-Z?]+\s+", "", line)
        if normalized and _looks_like_changed_path(normalized):
            files.append(normalized)
    return files


def _looks_like_changed_path(text: str) -> bool:
    if text.startswith("/") or text.startswith("./"):
        return True
    path = Path(text)
    return len(path.parts) > 1 or "." in path.name
