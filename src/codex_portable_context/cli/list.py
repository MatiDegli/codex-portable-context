"""Thin CLI for listing sessions from the derived mirror."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from codex_portable_context.core.discovery import default_out_dir
from codex_portable_context.core.index import load_index
from codex_portable_context.core.listing import (
    ListOptions,
    entries_to_json,
    filter_entries,
    render_entry_table,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for derived mirror listing."""

    parser = argparse.ArgumentParser(
        prog="python -m codex_portable_context.cli.list",
        description="List exported sessions from the derived Codex mirror.",
    )
    parser.add_argument("--out-dir", type=Path, help="Read the mirror from this directory.")
    parser.add_argument("--limit", type=int, default=0, help="Limit the number of listed sessions.")
    parser.add_argument(
        "--latest",
        action="store_true",
        help="Shortcut for a recent list view. Uses a limit of 10 unless --limit is set.",
    )
    parser.add_argument(
        "--title",
        default="",
        help="Filter by a case-insensitive title substring.",
    )
    parser.add_argument(
        "--id",
        default="",
        help="Filter by a case-insensitive session id substring.",
    )
    parser.add_argument("--summary", action="store_true", help="Show exported preview lines.")
    parser.add_argument(
        "--details",
        action="store_true",
        help="Show activity and environment lines.",
    )
    parser.add_argument("--redaction", action="store_true", help="Show compact redaction totals.")
    parser.add_argument("--json", action="store_true", help="Print filtered entries as JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the derived mirror list CLI."""

    args = build_parser().parse_args(argv)
    limit = args.limit
    if args.latest and limit == 0:
        limit = 10

    out_dir = (args.out_dir or default_out_dir()).expanduser().resolve()
    entries = load_index(out_dir)
    filtered = filter_entries(
        entries,
        ListOptions(
            limit=limit,
            title_filter=args.title,
            id_filter=args.id,
            show_summary=args.summary,
            show_details=args.details,
            show_redaction=args.redaction,
        ),
    )

    if not filtered:
        sys.stderr.write("No exported sessions matched the current filters.\n")
        return 1

    if args.json:
        sys.stdout.write(entries_to_json(filtered))
        return 0

    sys.stdout.write(
        render_entry_table(
            filtered,
            ListOptions(
                limit=limit,
                title_filter=args.title,
                id_filter=args.id,
                show_summary=args.summary,
                show_details=args.details,
                show_redaction=args.redaction,
            ),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
