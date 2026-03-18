"""Thin CLI for the Phase 3 Python mirror exporter."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from codex_portable_context.core.contract import HTML_INDEX_FILENAME, LANDING_FILENAME
from codex_portable_context.core.discovery import default_out_dir
from codex_portable_context.core.mirror import MirrorExportConfig, export_mirror
from codex_portable_context.providers import get_provider_adapter


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for the Python mirror exporter."""

    parser = argparse.ArgumentParser(
        prog="codex-session-mirror",
        description="Export a read-only derived mirror of local Codex sessions.",
        epilog=(
            "Examples:\n"
            "  codex-session-mirror\n"
            "  codex-session-mirror --redact\n"
            "  codex-session-mirror --out-dir ./out-custom\n"
            "  python -m codex_portable_context.cli.mirror --conversation-only"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
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
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable export result JSON to stdout.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the Phase 3 Python mirror exporter."""

    args = build_parser().parse_args(argv)
    provider = get_provider_adapter("codex")

    codex_home = (args.codex_home or provider.default_home_dir()).expanduser().resolve()
    source_dir = (args.source_dir or provider.default_source_dir(codex_home)).expanduser().resolve()
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
            provider=provider.provider_id,
            redact=args.redact,
            include_context=include_context,
            include_tools=include_tools,
            include_events=include_events,
        )
    )
    if args.json:
        payload = {
            "provider": provider.provider_id,
            "out_dir": str(result.out_dir),
            "session_count": result.session_count,
            "rendered_count": result.rendered_count,
            "reused_count": result.reused_count,
            "removed_count": result.removed_count,
            "redacted": result.redacted,
            "landing_relpath": LANDING_FILENAME,
            "reader_index_relpath": HTML_INDEX_FILENAME,
            "landing_path": str(result.out_dir / LANDING_FILENAME),
            "reader_index_path": str(result.out_dir / HTML_INDEX_FILENAME),
        }
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return 0

    sys.stdout.write(
        f"Mirror export complete: {result.session_count} sessions, "
        f"{result.rendered_count} rendered, {result.reused_count} reused, "
        f"{result.removed_count} removed -> {result.out_dir}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
