import json
import subprocess
from pathlib import Path

from codex_portable_context.cli.context_pack import main as context_pack_main
from codex_portable_context.cli.handoff import main as handoff_main
from codex_portable_context.core.mirror import MirrorExportConfig, export_mirror


def test_context_pack_cli_builds_derived_multi_session_manifest(
    tmp_path: Path,
    capsys,
) -> None:
    out_dir, repo_a, _repo_b = build_context_pack_fixture(tmp_path)
    generate_handoffs(out_dir, capsys, "session-alpha", "session-beta", "session-gamma")

    exit_code = context_pack_main(
        [
            "--out-dir",
            str(out_dir),
            "--repo-root",
            str(repo_a),
            "--latest",
            "2",
            "--json",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    manifest = json.loads(captured.out)
    assert manifest["kind"] == "codex_multi_session_context_pack"
    assert manifest["schema_version"] == 1
    assert manifest["status"] == "ready"
    assert manifest["contract"] == "roadmap_decomposition_context_pack_v1"
    assert manifest["contract_id"] == "roadmap_decomposition_context_pack_v1"
    assert manifest["advisory_only"] is True
    assert manifest["mode"] == "derived_handoff_manifest"
    assert manifest["authority_boundary"] == {
        "repo_local_authoritative": False,
        "historical_context_advisory": True,
        "live_resume": False,
        "raw_transcript_included": False,
        "transcript_excerpt_included": False,
        "reads_provider_raw_state": False,
        "moves_auth_config_runtime_state": False,
    }
    assert manifest["selection"]["source_scope"] == "existing_derived_handoffs_only"
    assert manifest["expected_handoff_dir"] == str(out_dir / "handoffs")
    assert manifest["selected_session_count"] == 2
    assert manifest["redaction_mode"] == "not_redacted"
    assert manifest["source_hashes"]["scope"] == "derived_artifacts_only"
    assert set(manifest["source_hashes"]["handoff_json_sha256_by_session"]) == {
        "session-alpha",
        "session-beta",
    }
    assert manifest["summary"]["included_sessions"] == 2
    assert manifest["summary"]["selected_session_count"] == 2
    assert manifest["summary"]["source_contract_counts"]["pass"] == 2
    assert manifest["summary"]["prompt_compliance_counts"]["pass"] == 2
    assert manifest["preflight"]["status"] == "ready"
    assert manifest["preflight"]["selected_session_count"] == 2

    session_ids = [item["session_id"] for item in manifest["sessions"]]
    assert session_ids == ["session-beta", "session-alpha"]
    assert {item["repo_root"] for item in manifest["sessions"]} == {str(repo_a)}

    first = manifest["sessions"][0]
    assert first["provider"] == "codex"
    assert first["available_sections"]["restart_prompt"] is True
    assert first["section_sources"]["restart_prompt"] == "derived_mirror"
    assert first["source_hashes"]["handoff_json_sha256"]
    assert len(first["source_hashes"]["handoff_json_sha256"]) == 64
    assert first["source_paths"]["handoff_json_relpath"] == "handoffs/session-beta.json"
    assert first["audit"]["prompt_compliance"]["status"] == "pass"
    assert first["audit"]["source_contract_compliance"]["status"] == "pass"
    memory_counts = first["sections"]["decisions_and_invariants"]["counts"]
    assert sum(memory_counts.values()) >= 1
    assert "open_loops" in first["sections"]
    assert "changed_artifacts" in first["sections"]
    assert "memory_available" in first["ranking"]["reasons"]

    assert manifest["authority_boundary"]["transcript_excerpt_included"] is False
    assert all("transcript_excerpt" not in item for item in manifest["sessions"])
    assert all("recent_window" not in item for item in manifest["sessions"])
    assert "raw provider transcripts" in " ".join(manifest["limitations"]).lower()


def test_context_pack_cli_filters_by_query_and_records_ranking_reason(
    tmp_path: Path,
    capsys,
) -> None:
    out_dir, _repo_a, _repo_b = build_context_pack_fixture(tmp_path)
    generate_handoffs(out_dir, capsys, "session-alpha", "session-beta", "session-gamma")

    exit_code = context_pack_main(
        [
            "--out-dir",
            str(out_dir),
            "--query",
            "reservation lane",
            "--latest",
            "0",
            "--json",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    manifest = json.loads(captured.out)
    assert [item["session_id"] for item in manifest["sessions"]] == ["session-beta"]
    assert manifest["sessions"][0]["ranking"]["score"] > 0
    assert "query_match" in manifest["sessions"][0]["ranking"]["reasons"]
    assert manifest["summary"]["filtered_counts"]["query_filter"] == 2


def test_context_pack_cli_requires_existing_handoffs(
    tmp_path: Path,
    capsys,
) -> None:
    out_dir, _repo_a, _repo_b = build_context_pack_fixture(tmp_path)

    exit_code = context_pack_main(
        [
            "--out-dir",
            str(out_dir),
            "--session-id",
            "session-alpha",
            "--json",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload["status"] == "blocked"
    assert payload["blocked_reason"] == "missing_handoff_json"
    assert payload["expected_handoff_dir"] == str(out_dir / "handoffs")
    assert payload["preflight"]["missing_handoff_count"] == 1
    assert payload["repair_guidance"]


def test_context_pack_cli_supports_require_redacted(
    tmp_path: Path,
    capsys,
) -> None:
    out_dir, _repo_a, _repo_b = build_context_pack_fixture(tmp_path, redact=True)
    generate_handoffs(out_dir, capsys, "session-alpha")

    exit_code = context_pack_main(
        [
            "--out-dir",
            str(out_dir),
            "--session-id",
            "session-alpha",
            "--require-redacted",
            "--json",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    manifest = json.loads(captured.out)
    assert manifest["summary"]["included_sessions"] == 1
    assert manifest["summary"]["redaction_counts"]["redacted"] == 1
    assert manifest["sessions"][0]["redaction_status"]["redacted"] is True
    assert manifest["sessions"][0]["redaction_status"]["report_available"] is True


def test_context_pack_cli_preflight_reports_missing_handoffs(
    tmp_path: Path,
    capsys,
) -> None:
    out_dir, repo_a, _repo_b = build_context_pack_fixture(tmp_path)
    generate_handoffs(out_dir, capsys, "session-alpha")

    exit_code = context_pack_main(
        [
            "--out-dir",
            str(out_dir),
            "--repo-root",
            str(repo_a),
            "--preflight",
            "--json",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload["kind"] == "codex_multi_session_context_pack_preflight"
    assert payload["status"] == "ready"
    assert payload["expected_handoff_dir"] == str(out_dir / "handoffs")
    assert payload["preflight"]["matching_handoff_count"] == 1
    assert payload["preflight"]["missing_handoff_count"] == 1
    assert payload["preflight"]["missing_expected_handoffs"][0]["session_id"] == "session-beta"


def test_context_pack_cli_preflight_blocks_when_no_handoffs_exist(
    tmp_path: Path,
    capsys,
) -> None:
    out_dir, repo_a, _repo_b = build_context_pack_fixture(tmp_path)

    exit_code = context_pack_main(
        [
            "--out-dir",
            str(out_dir),
            "--repo-root",
            str(repo_a),
            "--preflight",
            "--json",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    payload = json.loads(captured.out)
    assert payload["status"] == "blocked"
    assert payload["blocked_reason"] == "missing_handoff_json"
    assert payload["preflight"]["missing_handoff_count"] == 2
    assert "Generate the missing handoff JSON artifacts" in " ".join(
        payload["repair_guidance"]
    )


def test_context_pack_cli_accepts_curated_sessions_manifest(
    tmp_path: Path,
    capsys,
) -> None:
    out_dir, _repo_a, _repo_b = build_context_pack_fixture(tmp_path)
    generate_handoffs(out_dir, capsys, "session-beta")
    sessions_manifest = tmp_path / "curated-sessions.json"
    sessions_manifest.write_text(
        json.dumps({"sessions": [{"session_id": "session-beta"}]}),
        encoding="utf-8",
    )

    exit_code = context_pack_main(
        [
            "--out-dir",
            str(out_dir),
            "--sessions-manifest",
            str(sessions_manifest),
            "--json",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    manifest = json.loads(captured.out)
    assert [item["session_id"] for item in manifest["sessions"]] == ["session-beta"]
    assert manifest["selection"]["session_ids"] == ["session-beta"]
    assert "explicit_session_id_match" in manifest["sessions"][0]["ranking"]["reasons"]


def generate_handoffs(out_dir: Path, capsys, *session_ids: str) -> None:
    for session_id in session_ids:
        assert handoff_main(["--out-dir", str(out_dir), session_id]) == 0
        capsys.readouterr()


def build_context_pack_fixture(
    tmp_path: Path,
    *,
    redact: bool = False,
) -> tuple[Path, Path, Path]:
    repo_a = build_repo(tmp_path / "repo-a", "Repo A")
    repo_b = build_repo(tmp_path / "repo-b", "Repo B")
    codex_home = tmp_path / ".codex"
    source_dir = codex_home / "sessions" / "2026" / "04" / "01"
    source_dir.mkdir(parents=True)

    write_session(
        source_dir / "rollout-2026-04-01T10-00-00-alpha.jsonl",
        session_id="session-alpha",
        updated_at="2026-04-01T10:00:00Z",
        thread_name="Alpha Roadmap Session",
        cwd=repo_a,
        user_message="Review the roadmap decomposition boundary.",
        final_message=(
            "Decision: keep Workstation repo-local sources authoritative and use "
            "historical context as advisory only."
        ),
    )
    write_session(
        source_dir / "rollout-2026-04-01T10-05-00-beta.jsonl",
        session_id="session-beta",
        updated_at="2026-04-01T10:05:00Z",
        thread_name="Beta Reservation Session",
        cwd=repo_a,
        user_message="Evaluate the reservation lane for planner decomposition.",
        final_message=(
            "Decision: keep the reservation lane as advisory planner evidence. "
            "Invariant: raw provider transcripts stay excluded."
        ),
    )
    write_session(
        source_dir / "rollout-2026-04-01T10-10-00-gamma.jsonl",
        session_id="session-gamma",
        updated_at="2026-04-01T10:10:00Z",
        thread_name="Gamma Other Repo Session",
        cwd=repo_b,
        user_message="Review an unrelated repository task.",
        final_message="Decision: this belongs to a different repo root.",
    )

    (codex_home / "session_index.jsonl").write_text(
        "\n".join(
            json.dumps(record)
            for record in (
                {
                    "id": "session-alpha",
                    "thread_name": "Alpha Roadmap Session",
                    "updated_at": "2026-04-01T10:00:00Z",
                },
                {
                    "id": "session-beta",
                    "thread_name": "Beta Reservation Session",
                    "updated_at": "2026-04-01T10:05:00Z",
                },
                {
                    "id": "session-gamma",
                    "thread_name": "Gamma Other Repo Session",
                    "updated_at": "2026-04-01T10:10:00Z",
                },
            )
        )
        + "\n",
        encoding="utf-8",
    )

    out_dir = tmp_path / ("out-redacted" if redact else "out")
    export_mirror(
        MirrorExportConfig(
            codex_home=codex_home,
            source_dir=codex_home / "sessions",
            out_dir=out_dir,
            redact=redact,
        )
    )
    return out_dir, repo_a, repo_b


def write_session(
    path: Path,
    *,
    session_id: str,
    updated_at: str,
    thread_name: str,
    cwd: Path,
    user_message: str,
    final_message: str,
) -> None:
    developer_context = (
        "## Stable boundary\n\n"
        "- repo-local roadmap truth remains Workstation-owned\n"
        "- historical session context is advisory\n\n"
        "## Strategic decisions already made\n\n"
        "1. Raw provider transcripts must stay outside context packs.\n"
    )
    records = [
        {
            "timestamp": "2026-04-01T09:59:00Z",
            "type": "session_meta",
            "payload": {
                "id": session_id,
                "timestamp": "2026-04-01T09:59:00Z",
                "cwd": str(cwd),
                "originator": "codex_vscode",
                "cli_version": "0.200.0",
                "source": "vscode",
                "model_provider": "openai",
            },
        },
        {
            "timestamp": updated_at,
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "developer",
                "content": [{"type": "input_text", "text": developer_context}],
            },
        },
        {
            "timestamp": updated_at,
            "type": "event_msg",
            "payload": {"type": "user_message", "message": user_message},
        },
        {
            "timestamp": updated_at,
            "type": "event_msg",
            "payload": {
                "type": "agent_message",
                "message": f"I reviewed {thread_name}. {final_message}",
                "phase": "final_answer",
            },
        },
    ]
    path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )


def build_repo(root: Path, title: str) -> Path:
    root.mkdir(parents=True)
    (root / "README.md").write_text(f"# {title}\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "config", "user.email", "fixture@example.test"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Fixture"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(["git", "add", "."], cwd=root, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "commit", "-m", "fixture"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return root
