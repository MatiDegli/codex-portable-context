import subprocess
from pathlib import Path


def test_bash_wrapper_list_delegates_to_python(tmp_path: Path) -> None:
    out_dir = ensure_local_mirror()

    result = subprocess.run(
        ["bash", "scripts/codex-session-list", "--out-dir", str(out_dir), "--latest"],
        cwd=repo_root(),
        check=True,
        capture_output=True,
        text=True,
    )

    assert "SESSION ID" in result.stdout


def test_bash_wrapper_open_print_delegates_to_python() -> None:
    out_dir = ensure_local_mirror()

    result = subprocess.run(
        ["bash", "scripts/codex-session-open", "--out-dir", str(out_dir), "--latest", "--print"],
        cwd=repo_root(),
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip().endswith(".md")


def test_bash_wrapper_latest_print_delegates_to_python() -> None:
    out_dir = ensure_local_mirror()

    result = subprocess.run(
        [
            "bash",
            "scripts/codex-session-latest",
            "--out-dir",
            str(out_dir),
            "--metadata",
            "--print",
        ],
        cwd=repo_root(),
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip().endswith(".json")


def test_bash_wrapper_mirror_help_delegates_to_python() -> None:
    result = subprocess.run(
        ["bash", "scripts/codex-session-mirror", "--help"],
        cwd=repo_root(),
        check=True,
        capture_output=True,
        text=True,
    )

    assert "python -m codex_portable_context.cli.mirror" in result.stdout


def ensure_local_mirror() -> Path:
    out_dir = repo_root() / "out"
    if not out_dir.exists():
        subprocess.run(
            [
                "./.venv/bin/python",
                "-m",
                "codex_portable_context.cli.mirror",
                "--out-dir",
                str(out_dir),
            ],
            cwd=repo_root(),
            check=True,
            capture_output=True,
            text=True,
        )
    return out_dir


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]
