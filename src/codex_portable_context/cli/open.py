"""Thin CLI for opening or printing files from the derived mirror."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from codex_portable_context.core.discovery import default_out_dir
from codex_portable_context.core.index import (
    entry_brief_label,
    entry_path,
    latest_entry,
    load_index,
    require_landing_path,
)
from codex_portable_context.core.opening import open_file
from codex_portable_context.core.resolve import resolve_unique_entry


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for derived mirror opening."""

    parser = argparse.ArgumentParser(
        prog="python -m codex_portable_context.cli.open",
        description="Open or print a derived session export from the local mirror.",
    )
    parser.add_argument("--out-dir", type=Path, help="Read the mirror from this directory.")
    parser.add_argument(
        "--metadata",
        action="store_true",
        help="Target the metadata export instead of the Markdown transcript.",
    )
    parser.add_argument(
        "--print",
        action="store_true",
        help="Print the resolved path instead of opening it.",
    )
    parser.add_argument(
        "--landing",
        action="store_true",
        help="Open or print the mirror landing README.",
    )
    parser.add_argument(
        "--latest",
        action="store_true",
        help="Open or print the most recent exported session.",
    )
    parser.add_argument("selector", nargs="?", help="Full session id or unique id prefix.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the derived mirror open CLI."""

    args = build_parser().parse_args(argv)
    out_dir = (args.out_dir or default_out_dir()).expanduser().resolve()

    error = validate_args(
        open_landing=args.landing,
        open_latest=args.latest,
        selector=args.selector,
        metadata=args.metadata,
    )
    if error:
        sys.stderr.write(error + "\n")
        return 1

    if args.landing:
        target_path = require_landing_path(out_dir)
        if args.print:
            sys.stdout.write(f"{target_path}\n")
            return 0
        sys.stderr.write(f"Opening mirror landing: {target_path}\n")
        open_file(target_path)
        return 0

    entries = load_index(out_dir)
    if args.latest:
        entry = latest_entry(entries)
        if entry is None:
            sys.stderr.write(f"No exported sessions are available in {out_dir}\n")
            return 1
    else:
        assert args.selector is not None
        try:
            entry = resolve_unique_entry(entries, args.selector)
        except ValueError as exc:
            sys.stderr.write(f"{exc}\n")
            return 1

    target_kind = "metadata" if args.metadata else "markdown"
    target_path = entry_path(entry, target_kind, out_dir)
    if not target_path.is_file():
        sys.stderr.write(f"Derived file not found: {target_path}\n")
        sys.stderr.write("Re-run scripts/codex-session-mirror to refresh the mirror.\n")
        return 1

    if args.print:
        sys.stdout.write(f"{target_path}\n")
        return 0

    if args.latest:
        sys.stderr.write(f"Opening latest {target_kind}: {entry_brief_label(entry)}\n")
    else:
        sys.stderr.write(f"Opening {target_kind}: {entry_brief_label(entry)}\n")
    open_file(target_path)
    return 0


def validate_args(
    *,
    open_landing: bool,
    open_latest: bool,
    selector: str | None,
    metadata: bool,
) -> str | None:
    """Validate the CLI argument combinations."""

    if open_landing and open_latest:
        return "Use only one of --landing or --latest."
    if open_landing and metadata:
        return "--metadata cannot be combined with --landing."
    if not open_landing and not open_latest and not selector:
        return "Choose one of: --landing, --latest, or a session id/prefix."
    if (open_landing or open_latest) and selector:
        return "Do not pass a session selector with --landing or --latest."
    return None


if __name__ == "__main__":
    raise SystemExit(main())
