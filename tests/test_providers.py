from pathlib import Path

from codex_portable_context.providers import get_provider_adapter, registered_provider_ids


def test_provider_registry_exposes_codex_adapter() -> None:
    adapter = get_provider_adapter("codex")

    assert adapter.provider_id == "codex"
    assert "codex" in registered_provider_ids()
    assert adapter.capabilities()["supports_tools"] is True


def test_codex_adapter_filters_rollout_session_files(tmp_path: Path) -> None:
    source_dir = tmp_path / "sessions"
    source_dir.mkdir(parents=True)
    included = source_dir / "rollout-2026-03-16T10-00-00-session.jsonl"
    skipped = source_dir / "session.jsonl"
    included.write_text("", encoding="utf-8")
    skipped.write_text("", encoding="utf-8")

    adapter = get_provider_adapter("codex")

    assert [path.name for path in adapter.iter_session_files(source_dir)] == [included.name]
