"""Git repository state, tool-call parsing and failure signals."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

from ..parsing import ParsedSession, RenderBlock
from ..redaction import RedactionContext, redact_text
from .artifacts import (
    _normalize_artifact_path,
    _path_mentions_from_text,
    _updated_files_from_tool_output,
)
from .constants import RECENT_ACTION_LOOKBACK
from .utils import _excerpt_text, _parse_tool_call_json, _string


def _latest_failure_signal(
    parsed: ParsedSession | None,
    *,
    redacted: bool,
    context: RedactionContext,
) -> tuple[str, str]:
    if parsed is None:
        return ("none", "")

    calls_by_id = {
        block.call_id: block
        for block in parsed.conversation_entries
        if block.kind == "tool_call" and block.call_id
    }

    for block in reversed(parsed.conversation_entries[-20:]):
        if block.kind != "tool_output":
            continue
        failure_text = _tool_output_failure_text(block.text)
        if not failure_text:
            continue
        if redacted:
            failure_text = redact_text(failure_text, context).text
        command = ""
        source_call = calls_by_id.get(block.call_id or "")
        if source_call is not None:
            command = _expected_command_from_tool_call(source_call.text)
        return (_excerpt_text(failure_text, limit=180), command)

    if _has_unresolved_aborted_turn(parsed):
        return ("Latest turn ended in an aborted state.", "none")

    return ("none", "")


def _has_unresolved_aborted_turn(parsed: ParsedSession) -> bool:
    aborted_timestamp = ""
    for event in reversed(parsed.notable_events):
        if "turn_aborted" in event.label.lower():
            aborted_timestamp = event.timestamp or ""
            break

    if not aborted_timestamp:
        return False

    for event in parsed.notable_events:
        if (event.timestamp or "") <= aborted_timestamp:
            continue
        lowered = event.label.lower()
        if "task_complete" in lowered or "item_completed" in lowered:
            return False

    for block in parsed.conversation_entries:
        if (block.timestamp or "") <= aborted_timestamp:
            continue
        if block.kind in {"assistant", "tool_call", "tool_output"}:
            return False

    return True


def _normalized_action(
    block: RenderBlock,
    *,
    redacted: bool,
    context: RedactionContext,
) -> str:
    if block.kind == "tool_output" and "Updated the following files:" in block.text:
        files = _updated_files_from_tool_output(block.text)
        if files:
            rendered_files = ", ".join(files[:3])
            return f"updated {rendered_files}"

    if block.kind != "tool_call":
        return ""

    tool_name = block.tool_name or ""
    if tool_name != "exec_command":
        return ""

    payload = _parse_tool_call_json(block.text)
    cmd = _string(payload.get("cmd"))
    if not cmd:
        return ""

    if "./scripts/validate-python-v2" in cmd:
        return "ran ./scripts/validate-python-v2"
    if "codex-session-mirror" in cmd and "codex-session-handoff" in cmd:
        return "regenerated derived mirror"
    if "codex-session-mirror" in cmd:
        return "regenerated derived mirror"
    if "codex-session-handoff" in cmd:
        return ""
    if "handoffs/" in cmd or "Handoff Markdown" in cmd or "Jump to handoff" in cmd:
        return "verified reader links to handoffs/"
    if re.search(r"\bpytest\b|\bmypy\b|\bruff\b", cmd):
        return f"ran `{_excerpt_text(cmd, limit=80)}`"
    if re.fullmatch(r"\s*pwd\s*", cmd):
        return "ran `pwd`"
    return ""


def _infer_repo_cwd_from_session_paths(
    *,
    parsed: ParsedSession | None,
    summary: dict[str, Any],
) -> Path | None:
    candidate_paths = _absolute_session_path_candidates(parsed=parsed, summary=summary)
    if not candidate_paths:
        return None

    repo_counts: dict[str, int] = {}
    for candidate in candidate_paths:
        repo_root = _git_repo_root_for_path(candidate)
        if not repo_root:
            continue
        repo_counts[repo_root] = repo_counts.get(repo_root, 0) + 1

    if not repo_counts:
        return None
    ranked = sorted(repo_counts.items(), key=lambda item: item[1], reverse=True)
    if len(ranked) > 1 and ranked[0][1] <= ranked[1][1]:
        return None
    return Path(ranked[0][0])


def _absolute_session_path_candidates(
    *,
    parsed: ParsedSession | None,
    summary: dict[str, Any],
) -> list[Path]:
    candidates: list[Path] = []

    def append_candidate(raw_path: str) -> None:
        normalized = _normalize_artifact_path(raw_path)
        if not normalized:
            return
        path = Path(normalized).expanduser()
        if path.is_absolute():
            candidates.append(path)

    summary_values = [
        summary.get("preview"),
        summary.get("last_user_message"),
        summary.get("last_assistant_message"),
        summary.get("last_tool_summary"),
    ]
    for value in summary_values:
        for path in _path_mentions_from_text(_string(value)):
            append_candidate(path)

    if parsed is None:
        return candidates

    blocks = [
        *parsed.context_entries[-20:],
        *parsed.conversation_entries[-RECENT_ACTION_LOOKBACK:],
        *parsed.notable_events[-20:],
    ]
    for block in blocks:
        for path in _path_mentions_from_text(block.text):
            append_candidate(path)
        if block.kind != "tool_call":
            continue
        payload = _parse_tool_call_json(block.text)
        append_candidate(_string(payload.get("workdir")))
        append_candidate(_string(payload.get("cwd")))

    return candidates


def _git_repo_root_for_path(path: Path) -> str:
    candidate = path.expanduser()
    search_dir = candidate if candidate.exists() and candidate.is_dir() else candidate.parent
    if not search_dir.exists():
        return ""
    try:
        return subprocess.run(
            ["git", "-C", str(search_dir), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return ""


def _expected_command_from_tool_call(text: str) -> str:
    payload = _parse_tool_call_json(text)
    cmd = _string(payload.get("cmd"))
    if not cmd:
        return "none"
    return _excerpt_text(cmd, limit=120)


def _tool_output_failure_text(text: str) -> str:
    payload = _parse_tool_call_json(text)
    output = _string(payload.get("output")) or text
    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        exit_code = metadata.get("exit_code")
        if isinstance(exit_code, int) and exit_code != 0:
            return output or f"Command exited with code {exit_code}."
    return ""


def _detect_repo_state(cwd: Path | None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "repo_root": "",
        "repo_branch": "",
        "repo_head_commit": "",
        "repo_head_commit_date": "",
        "repo_root_source": "",
        "repo_clean": None,
        "repo_dirty_paths": [],
    }
    if cwd is None or not cwd.exists():
        return result

    try:
        repo_root = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        branch = subprocess.run(
            ["git", "-C", repo_root, "rev-parse", "--abbrev-ref", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        head_commit = subprocess.run(
            ["git", "-C", repo_root, "rev-parse", "--short", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        head_commit_date = subprocess.run(
            ["git", "-C", repo_root, "show", "-s", "--format=%cI", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "-C", repo_root, "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return result

    result.update(
        {
            "repo_root": repo_root,
            "repo_branch": branch,
            "repo_head_commit": head_commit,
            "repo_head_commit_date": head_commit_date,
            "repo_root_source": "metadata_cwd",
            "repo_clean": not bool(status),
            "repo_dirty_paths": _parse_git_status_paths(status),
        }
    )
    return result


def _parse_git_status_paths(status: str) -> list[dict[str, str]]:
    paths: list[dict[str, str]] = []
    for raw_line in status.splitlines():
        if not raw_line:
            continue
        status_code = raw_line[:2].strip() or "dirty"
        path_text = raw_line[2:].strip() if len(raw_line) > 2 else ""
        if " -> " in path_text:
            path_text = path_text.split(" -> ", 1)[1].strip()
        normalized = _normalize_artifact_path(path_text)
        if not normalized:
            continue
        paths.append({"path": normalized, "status": status_code})
    return paths
