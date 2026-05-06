"""Thin CLI for derived multi-session context packs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from codex_portable_context.core.context_pack import (
    DEFAULT_SECTION_ITEM_LIMIT,
    ContextPackOptions,
    build_context_pack,
    build_context_pack_blocked_response,
    build_context_pack_error,
    build_context_pack_preflight_response,
    render_context_pack_summary,
    write_context_pack,
)
from codex_portable_context.core.discovery import default_out_dir
from codex_portable_context.core.index import load_index


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for Workstation-oriented context packs."""

    parser = argparse.ArgumentParser(
        prog="codex-session-context-pack",
        description=(
            "Build a derived multi-session advisory context pack from existing handoff JSON."
        ),
        epilog=(
            "Examples:\n"
            "  codex-session-context-pack --repo-root /path/to/repo --latest 5 --json\n"
            "  codex-session-context-pack --out-dir .workstation/context/out --provider codex\n"
            "  codex-session-context-pack --session-id 019dcbe0 --json\n"
            "  codex-session-context-pack --sessions-manifest curated-sessions.json --json\n"
            "  codex-session-context-pack --repo-root /path/to/repo --preflight --json\n"
            "  codex-session-context-pack --query roadmap --since 2026-05-01T00:00:00Z\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        help="Read the derived mirror and existing handoffs from this directory.",
    )
    parser.add_argument(
        "--repo-root",
        default="",
        help="Include sessions whose derived repo root exactly matches this path.",
    )
    parser.add_argument(
        "--latest",
        type=int,
        default=5,
        help="Include this many latest/ranked sessions after filters. Use 0 for all matches.",
    )
    parser.add_argument(
        "--provider",
        default="",
        help="Include sessions from this provider id, such as codex or claude-code.",
    )
    parser.add_argument(
        "--session-id",
        action="append",
        default=[],
        help="Include a full session id or unique prefix. May be passed more than once.",
    )
    parser.add_argument(
        "--sessions-manifest",
        type=Path,
        help=(
            "Read curated session ids from JSON. Accepts a list, "
            "{session_ids: [...]}, or {sessions: [{session_id: ...}]}."
        ),
    )
    parser.add_argument(
        "--since",
        default="",
        help="Include sessions updated at/after this ISO time.",
    )
    parser.add_argument(
        "--until",
        default="",
        help="Include sessions updated at/before this ISO time.",
    )
    parser.add_argument(
        "--query",
        default="",
        help="Case-insensitive query over derived handoff text/metadata fields.",
    )
    parser.add_argument(
        "--require-redacted",
        action="store_true",
        help="Include only handoffs generated with redaction enabled.",
    )
    parser.add_argument(
        "--section-item-limit",
        type=int,
        default=DEFAULT_SECTION_ITEM_LIMIT,
        help="Maximum list items copied from each derived section.",
    )
    parser.add_argument(
        "--preflight",
        action="store_true",
        help=(
            "Report missing/invalid derived handoffs for this selection "
            "without emitting sessions."
        ),
    )
    parser.add_argument("--json", action="store_true", help="Print the manifest as JSON.")
    parser.add_argument("--write", type=Path, help="Write the JSON manifest to this path.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the derived multi-session context pack CLI."""

    args = build_parser().parse_args(argv)
    if args.latest < 0:
        sys.stderr.write("--latest must be zero or greater.\n")
        return 1
    if args.section_item_limit < 0:
        sys.stderr.write("--section-item-limit must be zero or greater.\n")
        return 1

    out_dir = (args.out_dir or default_out_dir()).expanduser().resolve()
    try:
        curated_session_ids = _session_ids_from_manifest(args.sessions_manifest)
    except (OSError, ValueError) as exc:
        error = build_context_pack_error(
            out_dir=out_dir,
            blocked_reason="invalid_sessions_manifest",
            repair_guidance=[
                (
                    "Pass a JSON array of session ids, {session_ids: [...]}, "
                    "or {sessions: [{session_id: ...}]}."
                ),
            ],
            detail=str(exc),
        )
        return _emit_error(error, json_mode=args.json)

    try:
        entries = load_index(out_dir)
    except FileNotFoundError as exc:
        error = build_context_pack_error(
            out_dir=out_dir,
            blocked_reason="missing_derived_index",
            repair_guidance=[
                "Populate the derived mirror index before building a context pack.",
                "This command will not read raw provider state to discover sessions.",
            ],
            detail=str(exc),
        )
        return _emit_error(error, json_mode=args.json)

    if not entries:
        error = build_context_pack_error(
            out_dir=out_dir,
            blocked_reason="no_exported_sessions",
            repair_guidance=[
                "Populate the derived mirror before building a context pack.",
                "This command will not read raw provider state to discover sessions.",
            ],
        )
        return _emit_error(error, json_mode=args.json)

    manifest = build_context_pack(
        entries,
        out_dir=out_dir,
        options=ContextPackOptions(
            latest=args.latest,
            repo_root=args.repo_root,
            provider=args.provider,
            session_ids=tuple([*args.session_id, *curated_session_ids]),
            query=args.query,
            since=args.since,
            until=args.until,
            require_redacted=bool(args.require_redacted),
            section_item_limit=args.section_item_limit,
        ),
    )

    if args.preflight:
        preflight = build_context_pack_preflight_response(manifest)
        if args.write:
            write_context_pack(preflight, args.write.expanduser())
        if args.json:
            sys.stdout.write(json.dumps(preflight, indent=2, ensure_ascii=False) + "\n")
        else:
            sys.stdout.write(_render_preflight(preflight))
        return 0 if preflight["status"] == "ready" else 1

    if not manifest["sessions"]:
        blocked = build_context_pack_blocked_response(manifest)
        if args.write:
            write_context_pack(blocked, args.write.expanduser())
        return _emit_error(blocked, json_mode=args.json)

    if args.write:
        write_context_pack(manifest, args.write.expanduser())

    if args.json:
        sys.stdout.write(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
        return 0

    sys.stdout.write(render_context_pack_summary(manifest))
    if args.write:
        sys.stderr.write(f"Context pack written: {args.write.expanduser()}\n")
    return 0


def _session_ids_from_manifest(path: Path | None) -> list[str]:
    if path is None:
        return []
    payload = json.loads(path.expanduser().read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return _session_ids_from_items(payload)
    if isinstance(payload, dict):
        if isinstance(payload.get("session_ids"), list):
            return _session_ids_from_items(payload["session_ids"])
        if isinstance(payload.get("sessions"), list):
            return _session_ids_from_items(payload["sessions"])
    raise ValueError("Unsupported curated sessions manifest shape.")


def _session_ids_from_items(items: list[object]) -> list[str]:
    session_ids: list[str] = []
    for item in items:
        if isinstance(item, str) and item.strip():
            session_ids.append(item.strip())
        elif isinstance(item, dict):
            value = item.get("session_id") or item.get("id")
            if isinstance(value, str) and value.strip():
                session_ids.append(value.strip())
    return session_ids


def _emit_error(error: dict[str, object], *, json_mode: bool) -> int:
    if json_mode:
        sys.stdout.write(json.dumps(error, indent=2, ensure_ascii=False) + "\n")
    else:
        sys.stderr.write(f"{error.get('blocked_reason')}: {error.get('detail') or ''}\n")
        guidance = error.get("repair_guidance")
        if isinstance(guidance, list):
            for item in guidance:
                sys.stderr.write(f"- {item}\n")
    return 1


def _render_preflight(payload: dict[str, object]) -> str:
    guidance = payload.get("repair_guidance")
    lines = [
        f"Preflight status: {payload.get('status')}",
        f"Blocked reason: {payload.get('blocked_reason') or '-'}",
        f"Expected handoff dir: {payload.get('expected_handoff_dir')}",
    ]
    if isinstance(guidance, list) and guidance:
        lines.append("Repair guidance:")
        lines.extend(f"- {item}" for item in guidance)
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
