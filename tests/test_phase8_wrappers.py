import json
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path


def test_installed_entrypoint_list_delegates_to_python(tmp_path: Path) -> None:
    out_dir = build_local_mirror(tmp_path)

    result = subprocess.run(
        [installed_command("codex-session-list"), "--out-dir", str(out_dir), "--latest"],
        cwd=repo_root(),
        check=True,
        capture_output=True,
        text=True,
    )

    assert "SESSION ID" in result.stdout


def test_installed_entrypoint_open_print_delegates_to_python(tmp_path: Path) -> None:
    out_dir = build_local_mirror(tmp_path)

    result = subprocess.run(
        [
            installed_command("codex-session-open"),
            "--out-dir",
            str(out_dir),
            "--latest",
            "--print",
        ],
        cwd=repo_root(),
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip().endswith(".md")


def test_installed_entrypoint_latest_print_delegates_to_python(tmp_path: Path) -> None:
    out_dir = build_local_mirror(tmp_path)

    result = subprocess.run(
        [
            installed_command("codex-session-latest"),
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


def test_installed_entrypoint_mirror_help_delegates_to_python() -> None:
    result = subprocess.run(
        [installed_command("codex-session-mirror"), "--help"],
        cwd=repo_root(),
        check=True,
        capture_output=True,
        text=True,
    )

    assert "codex-session-mirror" in result.stdout
    assert "Examples:" in result.stdout


def build_local_mirror(tmp_path: Path) -> Path:
    codex_home = tmp_path / ".codex"
    source_dir = codex_home / "sessions" / "2026" / "03" / "16"
    source_dir.mkdir(parents=True)

    session_path = source_dir / "rollout-2026-03-16T10-00-00-fixture-session.jsonl"
    records = [
        {
            "timestamp": "2026-03-16T10:00:00Z",
            "type": "session_meta",
            "payload": {
                "id": "session-1234",
                "timestamp": "2026-03-16T09:59:00Z",
                "cwd": "/home/tester/project",
                "originator": "codex_vscode",
                "cli_version": "0.200.0",
                "source": "vscode",
                "model_provider": "openai",
            },
        },
        {
            "timestamp": "2026-03-16T10:00:01Z",
            "type": "event_msg",
            "payload": {
                "type": "user_message",
                "message": "Please inspect the fixture session.",
            },
        },
        {
            "timestamp": "2026-03-16T10:00:02Z",
            "type": "event_msg",
            "payload": {
                "type": "agent_message",
                "message": "I will inspect the fixture session.",
                "phase": "commentary",
            },
        },
    ]
    session_path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )

    (codex_home / "session_index.jsonl").write_text(
        json.dumps(
            {
                "id": "session-1234",
                "thread_name": "Fixture Session",
                "updated_at": "2026-03-16T10:00:02Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    out_dir = tmp_path / "out"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "codex_portable_context.cli.mirror",
            "--codex-home",
            str(codex_home),
            "--source-dir",
            str(codex_home / "sessions"),
            "--out-dir",
            str(out_dir),
        ],
        cwd=repo_root(),
        check=True,
        capture_output=True,
        text=True,
    )
    return out_dir


def installed_command(name: str) -> str:
    scripts_dir = Path(sysconfig.get_path("scripts") or Path(sys.executable).parent)
    command = shutil.which(name, path=str(scripts_dir))
    if command is None:
        raise FileNotFoundError(
            f"Installed entrypoint not found: {name} under {scripts_dir}"
        )
    return command


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]
