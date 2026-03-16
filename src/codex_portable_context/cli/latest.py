"""Thin CLI for opening or printing the latest derived session export."""

from __future__ import annotations

import argparse

from codex_portable_context.cli.open import main as open_main


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for the latest-session helper."""

    parser = argparse.ArgumentParser(
        prog="codex-session-latest",
        description="Open or print the most recent exported session from the derived mirror.",
        epilog=(
            "Examples:\n"
            "  codex-session-latest\n"
            "  codex-session-latest --print\n"
            "  codex-session-latest --metadata --print\n"
            "  python -m codex_portable_context.cli.latest --out-dir ./out-redacted --print"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--out-dir", help="Read the mirror from this directory.")
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
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the latest-session helper by delegating to the open CLI."""

    args = build_parser().parse_args(argv)

    delegated_args = ["--latest"]
    if args.out_dir:
        delegated_args.extend(["--out-dir", args.out_dir])
    if args.metadata:
        delegated_args.append("--metadata")
    if args.print:
        delegated_args.append("--print")
    return open_main(delegated_args)


if __name__ == "__main__":
    raise SystemExit(main())
