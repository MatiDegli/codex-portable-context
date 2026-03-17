import json
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


def test_provider_registry_exposes_claude_code_adapter() -> None:
    adapter = get_provider_adapter("claude-code")
    capabilities = adapter.capabilities()

    assert adapter.provider_id == "claude-code"
    assert "claude-code" in registered_provider_ids()
    assert capabilities.supports_tools is False
    assert capabilities.supports_latest_selection is True


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


def test_codex_adapter_builds_source_context_from_session_index(tmp_path: Path) -> None:
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


def test_codex_adapter_describes_session_with_source_context_and_file_timestamp(
    tmp_path: Path,
) -> None:
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

    descriptor = adapter.describe_session(
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

    assert descriptor.provider == "codex"
    assert descriptor.provider_session_id == "session-1234"
    assert descriptor.session_id == "session-1234"
    assert descriptor.source_file == session_file
    assert descriptor.source_relpath == parsed.source_relpath
    assert descriptor.thread_name == "Fixture Session"
    assert descriptor.updated_at == "2026-03-16T10:00:06Z"


def test_claude_code_adapter_defaults_and_filters_primary_session_files(
    tmp_path: Path,
) -> None:
    adapter = get_provider_adapter("claude-code")
    home_dir = adapter.default_home_dir()
    source_dir = adapter.default_source_dir(tmp_path)

    assert home_dir.name == ".claude"
    assert source_dir == tmp_path / "projects"

    projects_dir = tmp_path / "projects"
    session_dir = projects_dir / "sample-project"
    subagents_dir = session_dir / "session-1234" / "subagents"
    session_dir.mkdir(parents=True)
    subagents_dir.mkdir(parents=True)
    primary = session_dir / "session-1234.jsonl"
    nested = session_dir / "session-1234" / "nested.jsonl"
    subagent = subagents_dir / "agent-1.jsonl"
    primary.write_text("", encoding="utf-8")
    nested.write_text("", encoding="utf-8")
    subagent.write_text("", encoding="utf-8")

    discovered = list(adapter.iter_session_files(projects_dir))

    assert discovered == [primary]


def test_claude_code_adapter_parses_conservative_session_fixture(tmp_path: Path) -> None:
    adapter = get_provider_adapter("claude-code")
    projects_dir = tmp_path / "projects"
    session_dir = projects_dir / "sample-project"
    session_dir.mkdir(parents=True)
    session_file = session_dir / "09bc645b-398f-4fc6-9889-c8120625a5b0.jsonl"
    records = [
        {
            "sessionId": "09bc645b-398f-4fc6-9889-c8120625a5b0",
            "cwd": r"c:\Criticos\Proyectos\PreciseOn\btc_trading_ai",
            "gitBranch": "main",
            "model": "claude-opus-4-6",
            "timestamp": "2026-03-17T12:00:00Z",
            "type": "session",
        },
        {
            "timestamp": "2026-03-17T12:00:05Z",
            "type": "message",
            "role": "user",
            "message": {"content": "Please inspect the project."},
        },
        {
            "timestamp": "2026-03-17T12:00:08Z",
            "type": "message",
            "role": "assistant",
            "model": "claude-opus-4-6",
            "message": {"content": "I will inspect it."},
        },
        {
            "timestamp": "2026-03-17T12:00:09Z",
            "type": "file-history-snapshot",
            "files": ["app.py"],
        },
    ]
    session_file.write_text(
        "\n".join(json.dumps(record) for record in records)
        + "\n",
        encoding="utf-8",
    )

    parsed = adapter.parse_session_file(session_file, projects_dir)
    descriptor = adapter.describe_session(
        parsed=parsed,
        source_context=ProviderSourceContext(),
        session_file=session_file,
    )

    assert parsed.provider == "claude-code"
    assert parsed.provider_session_id == "09bc645b-398f-4fc6-9889-c8120625a5b0"
    assert parsed.session_id == "09bc645b-398f-4fc6-9889-c8120625a5b0"
    assert parsed.cwd == r"c:\Criticos\Proyectos\PreciseOn\btc_trading_ai"
    assert parsed.source == "claude-code"
    assert parsed.model_provider == "anthropic"
    assert parsed.user_message_count == 1
    assert parsed.assistant_message_count == 1
    assert parsed.notable_event_count == 1
    assert parsed.user_messages == ["Please inspect the project."]
    assert parsed.assistant_messages == ["I will inspect it."]
    assert parsed.source_relpath == "sample-project/09bc645b-398f-4fc6-9889-c8120625a5b0.jsonl"
    assert descriptor.provider == "claude-code"
    assert descriptor.session_id == "09bc645b-398f-4fc6-9889-c8120625a5b0"
    assert descriptor.updated_at == "2026-03-17T12:00:09Z"
