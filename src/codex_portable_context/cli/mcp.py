"""Conservative CLI surface for the read-only MCP bridge helpers."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from codex_portable_context.mcp.bridge import (
    get_latest_session_summary,
    session_artifacts_get,
    session_handoff_get,
    session_list,
)


def build_parser() -> argparse.ArgumentParser:
    """Build a conservative parser for local bridge inspection only."""

    parser = argparse.ArgumentParser(
        prog="codex-session-mcp",
        description=(
            "Inspect the local read-only MCP bridge payloads. "
            "This command does not start a server, daemon, or network listener."
        ),
    )
    parser.add_argument("--out-dir", type=Path, help="Read the mirror from this directory.")
    subparsers = parser.add_subparsers(dest="command")

    list_parser = subparsers.add_parser(
        "session-list",
        help="Print the bridge session_list payload.",
    )
    list_parser.add_argument("--limit", type=int, default=0)
    list_parser.add_argument("--title", default="")
    list_parser.add_argument("--id", default="")

    subparsers.add_parser(
        "latest-session-summary",
        help="Print the bridge get_latest_session_summary payload.",
    )

    artifacts_parser = subparsers.add_parser(
        "session-artifacts-get",
        help="Print the bridge session_artifacts_get payload.",
    )
    artifacts_parser.add_argument("--session-id")
    artifacts_parser.add_argument("--latest", action="store_true")
    artifacts_parser.add_argument(
        "--no-handoff-paths",
        action="store_true",
        help="Omit expected handoff paths from the artifact bundle.",
    )
    artifacts_parser.add_argument("selector", nargs="?")

    handoff_parser = subparsers.add_parser(
        "session-handoff-get",
        help="Print the bridge session_handoff_get payload.",
    )
    handoff_parser.add_argument("--session-id")
    handoff_parser.add_argument("--latest", action="store_true")
    handoff_parser.add_argument("selector", nargs="?")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the conservative local MCP bridge CLI."""

    args = build_parser().parse_args(argv)
    if args.command is None:
        sys.stderr.write(
            "No MCP bridge action selected. Choose session-list, latest-session-summary, "
            "session-artifacts-get, or session-handoff-get.\n"
        )
        return 1

    if args.command == "session-list":
        payload = session_list(
            out_dir=args.out_dir,
            limit=args.limit,
            title_filter=args.title,
            id_filter=args.id,
        )
    elif args.command == "latest-session-summary":
        payload = get_latest_session_summary(out_dir=args.out_dir)
    elif args.command == "session-artifacts-get":
        payload = session_artifacts_get(
            out_dir=args.out_dir,
            session_id=args.session_id,
            selector=args.selector,
            latest=args.latest,
            include_handoff_paths=not args.no_handoff_paths,
        )
    else:
        payload = session_handoff_get(
            out_dir=args.out_dir,
            session_id=args.session_id,
            selector=args.selector,
            latest=args.latest,
        )

    sys.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
