"""Best-effort derived-output redaction helpers for the Python v2 exporter."""

from __future__ import annotations

import getpass
import os
import re
import socket
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class RedactionContext:
    """Environment-derived redaction context."""

    user_name: str
    home_dir: str
    hostname_short: str
    hostname_fqdn: str

    @classmethod
    def detect(cls) -> RedactionContext:
        user_name = (
            os.environ.get("USER")
            or os.environ.get("USERNAME")
            or getpass.getuser()
            or ""
        )
        home_dir = (
            os.environ.get("HOME")
            or os.environ.get("USERPROFILE")
            or str(Path.home())
        )
        hostname_short = socket.gethostname() or ""
        hostname_fqdn = socket.getfqdn() or hostname_short
        return cls(
            user_name=user_name,
            home_dir=home_dir,
            hostname_short=hostname_short,
            hostname_fqdn=hostname_fqdn,
        )


@dataclass(frozen=True, slots=True)
class RedactionResult:
    """Redacted text plus per-artifact replacement counts."""

    text: str
    report: dict[str, object]


def zero_artifact_report() -> dict[str, object]:
    """Return the zero-value artifact report shape."""

    return {
        "placeholder_counts": {
            "user": 0,
            "home": 0,
            "host": 0,
            "secret": 0,
        },
        "rule_counts": {
            "home_exact": 0,
            "home_exact_json": 0,
            "home_linux": 0,
            "home_macos": 0,
            "home_windows": 0,
            "home_windows_json": 0,
            "user_name": 0,
            "host_fqdn": 0,
            "host_at_short": 0,
            "host_key_short": 0,
            "secret_openai": 0,
            "secret_github": 0,
            "secret_github_pat": 0,
            "secret_aws_access_key": 0,
            "secret_bearer": 0,
            "secret_slack": 0,
        },
        "total_replacements": 0,
    }


def redact_text(text: str, context: RedactionContext) -> RedactionResult:
    """Apply conservative best-effort redaction to one derived text artifact."""

    redacted = text
    report = zero_artifact_report()
    placeholder_counts = report["placeholder_counts"]
    rule_counts = report["rule_counts"]
    assert isinstance(placeholder_counts, dict)
    assert isinstance(rule_counts, dict)

    for rule_name, placeholder_key, pattern, replacement, flags in build_rules(context):
        compiled = re.compile(pattern, flags)
        redacted, count = compiled.subn(replacement, redacted)
        rule_counts[rule_name] = count
        placeholder_counts[placeholder_key] = int(placeholder_counts[placeholder_key]) + count

    report["total_replacements"] = sum(int(value) for value in placeholder_counts.values())
    return RedactionResult(text=redacted, report=report)


def build_redaction_report(
    *,
    enabled: bool,
    metadata_report: dict[str, object],
    markdown_report: dict[str, object],
) -> dict[str, object]:
    """Build the contract-level redaction report object."""

    if not enabled:
        metadata_report = zero_artifact_report()
        markdown_report = zero_artifact_report()

    metadata_placeholders = metadata_report["placeholder_counts"]
    markdown_placeholders = markdown_report["placeholder_counts"]
    assert isinstance(metadata_placeholders, dict)
    assert isinstance(markdown_placeholders, dict)

    return {
        "enabled": enabled,
        "best_effort": True,
        "note": (
            "Counts reflect best-effort replacements detected in derived "
            "metadata and transcript content before redaction."
            if enabled
            else "Redaction mode was disabled for this export."
        ),
        "artifacts": {
            "metadata": metadata_report,
            "markdown": markdown_report,
        },
        "placeholder_totals": {
            "user": int(metadata_placeholders["user"]) + int(markdown_placeholders["user"]),
            "home": int(metadata_placeholders["home"]) + int(markdown_placeholders["home"]),
            "host": int(metadata_placeholders["host"]) + int(markdown_placeholders["host"]),
            "secret": int(metadata_placeholders["secret"]) + int(markdown_placeholders["secret"]),
        },
        "total_replacements": _artifact_total(metadata_report) + _artifact_total(markdown_report),
    }


def build_rules(
    context: RedactionContext,
) -> list[tuple[str, str, str, str, re.RegexFlag]]:
    """Return the ordered best-effort redaction rules."""

    rules: list[tuple[str, str, str, str, re.RegexFlag]] = []
    if context.home_dir:
        rules.append(
            (
                "home_exact",
                "home",
                re.escape(context.home_dir),
                "<redacted-home>",
                re.NOFLAG,
            )
        )
        if "\\" in context.home_dir:
            rules.append(
                (
                    "home_exact_json",
                    "home",
                    re.escape(context.home_dir.replace("\\", "\\\\")),
                    "<redacted-home>",
                    re.NOFLAG,
                )
            )
    rules.extend(
        [
            ("home_linux", "home", r"/home/[^/\s]+", "<redacted-home>", re.NOFLAG),
            ("home_macos", "home", r"/Users/[^/\s]+", "<redacted-home>", re.NOFLAG),
            (
                "home_windows",
                "home",
                r"[A-Za-z]:\\Users\\[^\\\s]+",
                "<redacted-home>",
                re.NOFLAG,
            ),
            (
                "home_windows_json",
                "home",
                r"[A-Za-z]:\\\\Users\\\\[^\\\s\"]+",
                "<redacted-home>",
                re.NOFLAG,
            ),
        ]
    )
    if context.user_name:
        rules.append(
            (
                "user_name",
                "user",
                rf"\b{re.escape(context.user_name)}\b",
                "<redacted-user>",
                re.NOFLAG,
            )
        )
    if context.hostname_fqdn and (
        "." in context.hostname_fqdn or context.hostname_fqdn != context.hostname_short
    ):
        rules.append(
            (
                "host_fqdn",
                "host",
                rf"\b{re.escape(context.hostname_fqdn)}\b",
                "<redacted-host>",
                re.NOFLAG,
            )
        )
    if context.hostname_short:
        rules.extend(
            [
                (
                    "host_at_short",
                    "host",
                    rf"@{re.escape(context.hostname_short)}\b",
                    "@<redacted-host>",
                    re.NOFLAG,
                ),
                (
                    "host_key_short",
                    "host",
                    rf"\b(hostname|host)\s*[:=]\s*{re.escape(context.hostname_short)}\b",
                    r"\1: <redacted-host>",
                    re.IGNORECASE,
                ),
            ]
        )
    rules.extend(
        [
            (
                "secret_openai",
                "secret",
                r"\bsk-[A-Za-z0-9_-]{16,}\b",
                "<redacted-secret>",
                re.NOFLAG,
            ),
            (
                "secret_github",
                "secret",
                r"\bgh[pousr]_[A-Za-z0-9]{20,}\b",
                "<redacted-secret>",
                re.NOFLAG,
            ),
            (
                "secret_github_pat",
                "secret",
                r"\bgithub_pat_[A-Za-z0-9_]{20,}\b",
                "<redacted-secret>",
                re.NOFLAG,
            ),
            (
                "secret_aws_access_key",
                "secret",
                r"\bAKIA[0-9A-Z]{16}\b",
                "<redacted-secret>",
                re.NOFLAG,
            ),
            (
                "secret_bearer",
                "secret",
                r"\bBearer\s+[A-Za-z0-9._-]{16,}\b",
                "Bearer <redacted-secret>",
                re.NOFLAG,
            ),
            (
                "secret_slack",
                "secret",
                r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b",
                "<redacted-secret>",
                re.NOFLAG,
            ),
        ]
    )
    return rules


def _artifact_total(report: dict[str, object]) -> int:
    value = report.get("total_replacements", 0)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    return 0
