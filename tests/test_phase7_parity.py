import json
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(
    shutil.which("jq") is None or shutil.which("perl") is None,
    reason="Bash parity checks require jq and perl.",
)
def test_bash_and_python_list_json_match(tmp_path: Path) -> None:
    codex_home = build_fixture_codex_home(tmp_path)
    out_dir = tmp_path / "out-bash"

    run_bash_mirror(codex_home, out_dir)

    bash_result = subprocess.run(
        [
            "bash",
            "scripts/codex-session-list",
            "--out-dir",
            str(out_dir),
            "--id",
            "session-1234",
            "--json",
        ],
        cwd=repo_root(),
        check=True,
        capture_output=True,
        text=True,
    )
    python_result = subprocess.run(
        [
            "./.venv/bin/python",
            "-m",
            "codex_portable_context.cli.list",
            "--out-dir",
            str(out_dir),
            "--id",
            "session-1234",
            "--json",
        ],
        cwd=repo_root(),
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(bash_result.stdout) == json.loads(python_result.stdout)


@pytest.mark.skipif(
    shutil.which("jq") is None or shutil.which("perl") is None,
    reason="Bash parity checks require jq and perl.",
)
def test_bash_and_python_open_print_match(tmp_path: Path) -> None:
    codex_home = build_fixture_codex_home(tmp_path)
    out_dir = tmp_path / "out-bash"

    run_bash_mirror(codex_home, out_dir)

    bash_open = subprocess.run(
        ["bash", "scripts/codex-session-open", "--out-dir", str(out_dir), "--latest", "--print"],
        cwd=repo_root(),
        check=True,
        capture_output=True,
        text=True,
    )
    python_open = subprocess.run(
        [
            "./.venv/bin/python",
            "-m",
            "codex_portable_context.cli.open",
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
    bash_latest = subprocess.run(
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
    python_latest = subprocess.run(
        [
            "./.venv/bin/python",
            "-m",
            "codex_portable_context.cli.latest",
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

    assert bash_open.stdout == python_open.stdout
    assert bash_latest.stdout == python_latest.stdout


@pytest.mark.skipif(
    shutil.which("jq") is None or shutil.which("perl") is None,
    reason="Bash parity checks require jq and perl.",
)
def test_bash_and_python_mirror_match_on_stable_metadata_fields(tmp_path: Path) -> None:
    codex_home = build_fixture_codex_home(tmp_path)
    out_bash = tmp_path / "out-bash"
    out_python = tmp_path / "out-python"

    run_bash_mirror(codex_home, out_bash)
    run_python_mirror(codex_home, out_python)

    bash_metadata_path = out_bash / "metadata" / "session-1234.json"
    python_metadata_path = out_python / "metadata" / "session-1234.json"
    bash_metadata = json.loads(bash_metadata_path.read_text(encoding="utf-8"))
    python_metadata = json.loads(python_metadata_path.read_text(encoding="utf-8"))

    stable_keys = [
        "session_id",
        "title",
        "export_profile",
        "thread_name",
        "updated_at",
        "source_relpath",
        "metadata_relpath",
        "markdown_relpath",
        "session_timestamp",
        "cwd",
        "originator",
        "source",
        "model_provider",
        "cli_version",
        "redacted",
        "markdown_includes",
        "event_count",
        "context_entry_count",
        "user_message_count",
        "assistant_message_count",
        "tool_call_count",
        "tool_output_count",
        "notable_event_count",
        "markdown_filter_rules",
    ]

    for key in stable_keys:
        assert bash_metadata[key] == python_metadata[key]


def build_fixture_codex_home(tmp_path: Path) -> Path:
    codex_home = tmp_path / ".codex"
    source_dir = codex_home / "sessions" / "2026" / "03" / "16"
    source_dir.mkdir(parents=True)

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
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "developer",
                "content": [{"type": "input_text", "text": "Developer context."}],
            },
        },
        {
            "timestamp": "2026-03-16T10:00:02Z",
            "type": "event_msg",
            "payload": {
                "type": "user_message",
                "message": "Please inspect /home/tester/project and C:\\Users\\tester\\project.",
            },
        },
        {
            "timestamp": "2026-03-16T10:00:03Z",
            "type": "event_msg",
            "payload": {
                "type": "agent_message",
                "message": "I will inspect the workspace.",
                "phase": "commentary",
            },
        },
        {
            "timestamp": "2026-03-16T10:00:04Z",
            "type": "response_item",
            "payload": {
                "type": "function_call",
                "name": "exec_command",
                "call_id": "call-1",
                "arguments": json.dumps({"cmd": "pwd", "workdir": "/home/tester/project"}),
            },
        },
        {
            "timestamp": "2026-03-16T10:00:05Z",
            "type": "response_item",
            "payload": {
                "type": "function_call_output",
                "call_id": "call-1",
                "output": "/home/tester/project\nC:\\Users\\tester\\project\n",
            },
        },
        {
            "timestamp": "2026-03-16T10:00:06Z",
            "type": "event_msg",
            "payload": {
                "type": "task_complete",
                "turn_id": "turn-1",
                "status": "completed",
            },
        },
    ]
    (source_dir / "rollout-2026-03-16T10-00-00-session-1234.jsonl").write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )
    (codex_home / "session_index.jsonl").write_text(
        json.dumps(
            {
                "id": "session-1234",
                "thread_name": "Fixture Session",
                "updated_at": "2026-03-16T10:00:06Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return codex_home


def run_bash_mirror(codex_home: Path, out_dir: Path) -> None:
    subprocess.run(
        [
            "bash",
            "scripts/codex-session-mirror",
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


def run_python_mirror(codex_home: Path, out_dir: Path) -> None:
    subprocess.run(
        [
            "./.venv/bin/python",
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


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]
