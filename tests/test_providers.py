from pathlib import Path

import pytest

from codex_portable_context.core.parsing import ParsedSession
from codex_portable_context.providers import get_provider_adapter, registered_provider_ids
from codex_portable_context.providers.base import ProviderSourceContext


def test_provider_registry_exposes_codex_adapter() -> None:
    adapter = get_provider_adapter("codex")
    capabilities = adapter.capabilities()

    assert adapter.provider_id == "codex"
    assert "codex" in registered_provider_ids()
    assert capabilities.supports_tools is True
    assert capabilities.supports_handoff_source_enrichment is True


def test_codex_adapter_resolves_default_home_and_source_dirs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = get_provider_adapter("codex")
    monkeypatch.setenv("CODEX_HOME", "~/custom-codex-home")

    home_dir = adapter.default_home_dir()
    source_dir = adapter.default_source_dir(home_dir)

    assert home_dir == Path("~/custom-codex-home").expanduser()
    assert source_dir == home_dir / "sessions"


def test_codex_adapter_filters_rollout_session_files(tmp_path: Path) -> None:
    source_dir = tmp_path / "sessions"
    source_dir.mkdir(parents=True)
    included = source_dir / "rollout-2026-03-16T10-00-00-session.jsonl"
    skipped = source_dir / "session.jsonl"
    included.write_text("", encoding="utf-8")
    skipped.write_text("", encoding="utf-8")

    adapter = get_provider_adapter("codex")

    assert [path.name for path in adapter.iter_session_files(source_dir)] == [included.name]


def test_codex_adapter_builds_source_context_from_session_index(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    home_dir = tmp_path / "codex-home"
    home_dir.mkdir()
    session_index = home_dir / "session_index.jsonl"
    session_index.write_text(
        (
            '{"id":"session-1234","thread_name":"Fixture Session",'
            '"updated_at":"2026-03-16T10:00:06Z"}\n'
        ),
        encoding="utf-8",
    )

    adapter = get_provider_adapter("codex")
    context = adapter.build_source_context(home_dir)

    assert context.native_index_by_session_id == {
        "session-1234": {
            "id": "session-1234",
            "thread_name": "Fixture Session",
            "updated_at": "2026-03-16T10:00:06Z",
        }
    }


def test_codex_adapter_session_hints_use_source_context_and_file_timestamp(tmp_path: Path) -> None:
    session_file = tmp_path / "rollout-2026-03-16T10-00-00-session.jsonl"
    session_file.write_text("", encoding="utf-8")
    adapter = get_provider_adapter("codex")
    parsed = ParsedSession(
        provider="codex",
        provider_session_id="session-1234",
        source_file=session_file,
        source_relpath="2026/03/16/rollout-2026-03-16T10-00-00-session.jsonl",
        session_id="session-1234",
        session_timestamp="2026-03-16T09:59:00Z",
        cwd=None,
        originator=None,
        source=None,
        model_provider=None,
        cli_version=None,
        context_entries=[],
        conversation_entries=[],
        notable_events=[],
        user_messages=[],
        assistant_messages=[],
        event_count=0,
        context_entry_count=0,
        user_message_count=0,
        assistant_message_count=0,
        tool_call_count=0,
        tool_output_count=0,
        notable_event_count=0,
    )

    hints = adapter.session_hints(
        parsed=parsed,
        source_context=ProviderSourceContext(
            native_index_by_session_id={
                "session-1234": {
                    "thread_name": "Fixture Session",
                    "updated_at": "2026-03-16T10:00:06Z",
                }
            }
        ),
        session_file=session_file,
    )

    assert hints.thread_name == "Fixture Session"
    assert hints.updated_at == "2026-03-16T10:00:06Z"
