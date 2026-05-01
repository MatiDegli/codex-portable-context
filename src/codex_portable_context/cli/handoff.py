"""Thin CLI for generating extractive handoff bundles from the derived mirror."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from codex_portable_context.core.discovery import default_out_dir
from codex_portable_context.core.handoff import generate_handoff
from codex_portable_context.core.index import latest_entry, load_index
from codex_portable_context.core.resolve import resolve_unique_entry


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for handoff bundle generation."""

    parser = argparse.ArgumentParser(
        prog="codex-session-handoff",
        description="Generate an extractive handoff bundle from the derived mirror.",
        epilog=(
            "Examples:\n"
            "  codex-session-handoff --latest\n"
            "  codex-session-handoff 019cef3a --print\n"
            "  codex-session-handoff 019cef3a --restart-prompt\n"
            "  python -m codex_portable_context.cli.handoff --latest --out-dir ./out-redacted"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        help="Read and write bundle artifacts in this mirror.",
    )
    parser.add_argument(
        "--latest",
        action="store_true",
        help="Generate a handoff for the most recent exported session.",
    )
    parser.add_argument(
        "--print",
        action="store_true",
        help="Print the generated Markdown handoff path instead of a summary line.",
    )
    parser.add_argument(
        "--restart-prompt",
        action="store_true",
        help="Print only the generated fresh-session restart prompt text.",
    )
    parser.add_argument("selector", nargs="?", help="Full session id or unique id prefix.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the handoff bundle generator."""

    args = build_parser().parse_args(argv)
    out_dir = (args.out_dir or default_out_dir()).expanduser().resolve()

    if args.print and args.restart_prompt:
        sys.stderr.write("Use only one of --print or --restart-prompt.\n")
        return 1
    if args.latest and args.selector:
        sys.stderr.write("Do not pass a session selector with --latest.\n")
        return 1
    if not args.latest and not args.selector:
        sys.stderr.write("Choose --latest or pass a session id/prefix.\n")
        return 1

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

    result = generate_handoff(entry, out_dir)
    if args.print:
        sys.stdout.write(f"{result.markdown_path}\n")
        return 0
    if args.restart_prompt:
        sys.stdout.write(_restart_prompt_text(result.json_path) + "\n")
        return 0

    sys.stdout.write(
        "Handoff bundle written: "
        f"{result.markdown_path} and {result.json_path}\n"
    )
    return 0


def _restart_prompt_text(json_path: Path) -> str:
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    restart_prompt = payload.get("restart_prompt")
    if not isinstance(restart_prompt, dict):
        return ""
    text = restart_prompt.get("text")
    return text if isinstance(text, str) else ""


if __name__ == "__main__":
    raise SystemExit(main())
