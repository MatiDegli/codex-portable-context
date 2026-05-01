"""Thin CLI for auditing generated handoff memory quality."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from codex_portable_context.core.discovery import default_out_dir
from codex_portable_context.core.handoff_audit import (
    HandoffAuditOptions,
    audit_handoffs,
    render_handoff_audit,
    write_e2e_manifest,
)
from codex_portable_context.core.index import load_index


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for handoff quality audits."""

    parser = argparse.ArgumentParser(
        prog="codex-session-handoff-audit",
        description="Audit Decisions / Invariants coverage for generated handoffs.",
        epilog=(
            "Examples:\n"
            "  codex-session-handoff-audit --limit 20\n"
            "  codex-session-handoff-audit 019dcbe0 019ddab2\n"
            "  codex-session-handoff-audit --json --no-generate\n"
            "  codex-session-handoff-audit --write-e2e-manifest out/e2e.json 019dcbe0"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--out-dir", type=Path, help="Read the mirror from this directory.")
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Audit this many latest unique sessions when no selectors are passed.",
    )
    parser.add_argument(
        "--no-generate",
        action="store_true",
        help="Read existing handoff JSON files instead of regenerating them first.",
    )
    parser.add_argument("--json", action="store_true", help="Print the audit report as JSON.")
    parser.add_argument(
        "--write-e2e-manifest",
        type=Path,
        help=(
            "Write a manual-only restart-prompt E2E manifest for the selected "
            "sessions. This does not launch agents or send messages."
        ),
    )
    parser.add_argument("selectors", nargs="*", help="Full session ids or unique id prefixes.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the handoff quality audit CLI."""

    args = build_parser().parse_args(argv)
    if args.limit < 0:
        sys.stderr.write("--limit must be zero or greater.\n")
        return 1

    out_dir = (args.out_dir or default_out_dir()).expanduser().resolve()
    entries = load_index(out_dir)
    if not entries:
        sys.stderr.write(f"No exported sessions are available in {out_dir}\n")
        return 1

    try:
        report = audit_handoffs(
            entries,
            out_dir=out_dir,
            options=HandoffAuditOptions(
                limit=args.limit,
                selectors=tuple(args.selectors),
                generate=not args.no_generate,
            ),
        )
    except ValueError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1

    if args.json:
        sys.stdout.write(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    else:
        sys.stdout.write(render_handoff_audit(report))
    if args.write_e2e_manifest:
        manifest_path = write_e2e_manifest(report, args.write_e2e_manifest.expanduser())
        sys.stderr.write(f"E2E manifest written: {manifest_path}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
