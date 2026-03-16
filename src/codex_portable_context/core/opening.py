"""Cross-platform file opening helpers for the Python v2 core."""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


def preferred_editor_command() -> list[str] | None:
    """Return the preferred editor command from VISUAL or EDITOR."""

    for variable in ("VISUAL", "EDITOR"):
        value = os.environ.get(variable)
        if value:
            return shlex.split(value)
    return None


def open_file(path: Path) -> None:
    """Open a derived file using the best available cross-platform strategy."""

    editor_command = preferred_editor_command()
    if editor_command:
        subprocess.run([*editor_command, str(path)], check=True)
        return

    if sys.platform.startswith("win") and hasattr(os, "startfile"):
        os.startfile(str(path))  # type: ignore[attr-defined]
        return

    if sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=True)
        return

    if (
        shutil.which("xdg-open")
        and (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    ):
        subprocess.Popen(
            ["xdg-open", str(path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return

    pager = shutil.which("less")
    if pager:
        subprocess.run([pager, str(path)], check=True)
        return

    sys.stdout.write(path.read_text(encoding="utf-8"))
