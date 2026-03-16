"""Thin CLI for the Phase 3 Python mirror exporter."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from codex_portable_context.core.discovery import (
    default_codex_home,
    default_out_dir,
    default_source_dir,
)
from codex_portable_context.core.mirror import MirrorExportConfig, export_mirror


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for the Python mirror exporter."""

    parser = argparse.ArgumentParser(
        prog="python -m codex_portable_context.cli.mirror",
        description="Export a read-only derived mirror of local Codex sessions.",
    )
    parser.add_argument(
        "--codex-home",
        type=Path,
        help="Override the local Codex home directory.",
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        help="Override the raw session source directory.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        help="Write the derived mirror into this directory.",
    )
    parser.add_argument(
        "--redact",
        action="store_true",
        help="Apply best-effort redaction to derived output only.",
    )
    parser.add_argument(
        "--no-context",
        action="store_true",
        help="Omit session context from the derived Markdown.",
    )
    parser.add_argument(
        "--no-tools",
        action="store_true",
        help="Omit tool calls and tool outputs from the derived Markdown.",
    )
    parser.add_argument(
        "--no-events",
        action="store_true",
        help="Omit notable lifecycle events from the derived Markdown.",
    )
    parser.add_argument(
        "--conversation-only",
        action="store_true",
        help="Shortcut for --no-context --no-tools --no-events.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the Phase 3 Python mirror exporter."""

    args = build_parser().parse_args(argv)

    codex_home = (args.codex_home or default_codex_home()).expanduser().resolve()
    source_dir = (args.source_dir or default_source_dir(codex_home)).expanduser().resolve()
    if args.out_dir:
        out_dir = args.out_dir.expanduser().resolve()
    elif args.redact:
        out_dir = (default_out_dir().parent / "out-redacted").resolve()
    else:
        out_dir = default_out_dir().resolve()

    include_context = not args.no_context
    include_tools = not args.no_tools
    include_events = not args.no_events
    if args.conversation_only:
        include_context = False
        include_tools = False
        include_events = False

    result = export_mirror(
        MirrorExportConfig(
            codex_home=codex_home,
            source_dir=source_dir,
            out_dir=out_dir,
            redact=args.redact,
            include_context=include_context,
            include_tools=include_tools,
            include_events=include_events,
        )
    )
    sys.stdout.write(
        f"Mirror export complete: {result.session_count} sessions, "
        f"{result.rendered_count} rendered, {result.reused_count} reused, "
        f"{result.removed_count} removed -> {result.out_dir}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
