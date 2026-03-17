"""Mirror export orchestration for the Python v2 CLI."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from codex_portable_context.providers import get_provider_adapter

from .contract import LANDING_MARKER, MARKDOWN_FILTER_RULES
from .discovery import mirror_layout
from .html_reader import render_reader_index, render_session_reader
from .index import sort_entries
from .markdown import render_landing, render_session_markdown
from .parsing import ParsedSession
from .redaction import RedactionContext, build_redaction_report, redact_text
from .state import StateRecord, build_input_signature, load_state, save_state
from .summaries import build_summary, derive_session_title


@dataclass(frozen=True, slots=True)
class MirrorExportConfig:
    """Configuration for one derived mirror export run."""

    codex_home: Path
    source_dir: Path
    out_dir: Path
    provider: str = "codex"
    redact: bool = False
    include_context: bool = True
    include_tools: bool = True
    include_events: bool = True

    @property
    def export_profile(self) -> str:
        if not self.include_context and not self.include_tools and not self.include_events:
            return "conversation-only"
        if self.include_context and self.include_tools and self.include_events:
            return "full"
        return "custom"


@dataclass(frozen=True, slots=True)
class MirrorExportResult:
    """Summary of one derived mirror export run."""

    out_dir: Path
    rendered_count: int
    reused_count: int
    removed_count: int
    session_count: int
    redacted: bool


def export_mirror(config: MirrorExportConfig) -> MirrorExportResult:
    """Export the derived mirror for the chosen raw session source."""

    layout = mirror_layout(config.out_dir)
    _prepare_layout(layout)
    provider = get_provider_adapter(config.provider)

    source_context = provider.build_source_context(config.codex_home)
    redaction_context = RedactionContext.detect()
    previous_state = load_state(layout.state_path)

    index_entries: list[dict[str, Any]] = []
    next_state: list[StateRecord] = []
    seen_relpaths: set[str] = set()
    rendered_count = 0
    reused_count = 0
    removed_count = 0

    for session_file in provider.iter_session_files(config.source_dir):
        parsed = provider.parse_session_file(session_file, config.source_dir)
        descriptor = provider.describe_session(
            parsed=parsed,
            source_context=source_context,
            session_file=session_file,
        )
        thread_name = descriptor.thread_name
        updated_at = descriptor.updated_at
        source_relpath = descriptor.source_relpath
        seen_relpaths.add(source_relpath)

        metadata_relpath = layout.metadata_relpath(descriptor.session_id)
        markdown_relpath = layout.markdown_relpath(descriptor.session_id)
        signature = build_input_signature(
            source_file=session_file,
            session_id=descriptor.session_id,
            thread_name=thread_name,
            updated_at=updated_at,
            redact=config.redact,
            profile_name=config.export_profile,
            include_context=config.include_context,
            include_tools=config.include_tools,
            include_events=config.include_events,
            redaction_context=redaction_context,
        )

        previous = previous_state.get(source_relpath)
        metadata_path = layout.out_dir / metadata_relpath
        markdown_path = layout.out_dir / markdown_relpath
        if (
            previous
            and previous.input_signature == signature
            and metadata_path.is_file()
            and markdown_path.is_file()
            and layout.reader_path(descriptor.session_id).is_file()
        ):
            index_entries.append(_load_json(metadata_path))
            next_state.append(
                StateRecord(
                    source_relpath=source_relpath,
                    input_signature=signature,
                    session_id=descriptor.session_id,
                    metadata_relpath=metadata_relpath,
                    markdown_relpath=markdown_relpath,
                    reader_relpath=layout.reader_relpath(descriptor.session_id),
                )
            )
            reused_count += 1
            continue

        metadata_entry = _render_session_export(
            parsed=parsed,
            descriptor=descriptor,
            thread_name=thread_name,
            updated_at=updated_at,
            layout=layout,
            config=config,
            redaction_context=redaction_context,
        )
        index_entries.append(metadata_entry)
        next_state.append(
            StateRecord(
                source_relpath=source_relpath,
                input_signature=signature,
                session_id=descriptor.session_id,
                metadata_relpath=metadata_relpath,
                markdown_relpath=markdown_relpath,
                reader_relpath=layout.reader_relpath(descriptor.session_id),
            )
        )
        rendered_count += 1

    for source_relpath, previous in previous_state.items():
        if source_relpath in seen_relpaths:
            continue
        metadata_removed = _remove_if_present(layout.out_dir / previous.metadata_relpath)
        markdown_removed = _remove_if_present(layout.out_dir / previous.markdown_relpath)
        reader_removed = _remove_if_present(layout.out_dir / previous.reader_relpath)
        if metadata_removed or markdown_removed or reader_removed:
            removed_count += 1

    ordered_entries = sort_entries(index_entries)
    _write_index(layout.index_path, ordered_entries)
    mirror_exported_at = _iso_now()
    _write_reader_index(
        path=layout.reader_index_path,
        entries=ordered_entries,
        exported_at=mirror_exported_at,
        redacted_export=config.redact,
    )
    landing = render_landing(
        entries=ordered_entries,
        exported_at=mirror_exported_at,
        redacted_export=config.redact,
    )
    _write_landing(layout.landing_path, landing)
    save_state(layout.state_path, next_state)

    return MirrorExportResult(
        out_dir=layout.out_dir,
        rendered_count=rendered_count,
        reused_count=reused_count,
        removed_count=removed_count,
        session_count=len(ordered_entries),
        redacted=config.redact,
    )


def _prepare_layout(layout: Any) -> None:
    layout.out_dir.mkdir(parents=True, exist_ok=True)
    layout.metadata_dir.mkdir(parents=True, exist_ok=True)
    layout.sessions_dir.mkdir(parents=True, exist_ok=True)
    layout.reader_dir.mkdir(parents=True, exist_ok=True)


def _render_session_export(
    *,
    parsed: ParsedSession,
    descriptor: Any,
    thread_name: str | None,
    updated_at: str | None,
    layout: Any,
    config: MirrorExportConfig,
    redaction_context: RedactionContext,
) -> dict[str, Any]:
    title = derive_session_title(parsed, thread_name)
    summary = build_summary(parsed)
    exported_at = _iso_now()
    metadata_entry = {
        "provider": descriptor.provider,
        "provider_session_id": descriptor.provider_session_id,
        "session_id": descriptor.session_id,
        "title": title,
        "export_profile": config.export_profile,
        "thread_name": thread_name,
        "exported_at": exported_at,
        "updated_at": updated_at,
        "source_file": str(descriptor.source_file),
        "source_relpath": descriptor.source_relpath,
        "metadata_relpath": layout.metadata_relpath(descriptor.session_id),
        "markdown_relpath": layout.markdown_relpath(descriptor.session_id),
        "reader_relpath": layout.reader_relpath(descriptor.session_id),
        "session_timestamp": parsed.session_timestamp,
        "cwd": parsed.cwd,
        "originator": parsed.originator,
        "source": parsed.source,
        "model_provider": parsed.model_provider,
        "cli_version": parsed.cli_version,
        "redacted": config.redact,
        "markdown_includes": {
            "context": config.include_context,
            "tools": config.include_tools,
            "events": config.include_events,
        },
        "summary": summary,
        "event_count": parsed.event_count,
        "context_entry_count": parsed.context_entry_count,
        "user_message_count": parsed.user_message_count,
        "assistant_message_count": parsed.assistant_message_count,
        "tool_call_count": parsed.tool_call_count,
        "tool_output_count": parsed.tool_output_count,
        "notable_event_count": parsed.notable_event_count,
        "markdown_filter_rules": list(MARKDOWN_FILTER_RULES),
    }

    markdown_text = render_session_markdown(
        parsed=parsed,
        title=title,
        thread_name=thread_name,
        updated_at=updated_at,
        export_profile=config.export_profile,
        summary=summary,
        include_context=config.include_context,
        include_tools=config.include_tools,
        include_events=config.include_events,
    )
    metadata_without_report = json.dumps(metadata_entry, indent=2, ensure_ascii=False) + "\n"

    if config.redact:
        metadata_artifact = redact_text(metadata_without_report, redaction_context)
        markdown_artifact = redact_text(markdown_text, redaction_context)
        report = build_redaction_report(
            enabled=True,
            metadata_report=metadata_artifact.report,
            markdown_report=markdown_artifact.report,
        )
        metadata_entry["redaction_report"] = report
        final_metadata = redact_text(
            json.dumps(metadata_entry, indent=2, ensure_ascii=False) + "\n",
            redaction_context,
        ).text
        final_markdown = markdown_artifact.text
    else:
        report = build_redaction_report(
            enabled=False,
            metadata_report={},
            markdown_report={},
        )
        metadata_entry["redaction_report"] = report
        final_metadata = json.dumps(metadata_entry, indent=2, ensure_ascii=False) + "\n"
        final_markdown = markdown_text

    metadata_path = layout.metadata_path(descriptor.session_id)
    markdown_path = layout.markdown_path(descriptor.session_id)
    reader_path = layout.reader_path(descriptor.session_id)
    metadata_path.write_text(final_metadata, encoding="utf-8")
    markdown_path.write_text(final_markdown, encoding="utf-8")
    written_metadata = _load_json(metadata_path)
    reader_path.write_text(
        render_session_reader(
            entry=written_metadata,
            metadata_text=final_metadata,
            markdown_text=final_markdown,
        ),
        encoding="utf-8",
    )
    return written_metadata


def _write_index(path: Path, entries: list[dict[str, Any]]) -> None:
    text = ""
    if entries:
        text = "\n".join(
            json.dumps(entry, separators=(",", ":"), ensure_ascii=False) for entry in entries
        )
        text += "\n"
    path.write_text(text, encoding="utf-8")


def _write_reader_index(
    *,
    path: Path,
    entries: list[dict[str, Any]],
    exported_at: str,
    redacted_export: bool,
) -> None:
    path.write_text(
        render_reader_index(
            entries=entries,
            exported_at=exported_at,
            redacted_export=redacted_export,
        ),
        encoding="utf-8",
    )


def _write_landing(path: Path, text: str) -> None:
    if path.is_file() and LANDING_MARKER not in path.read_text(encoding="utf-8"):
        raise ValueError(
            f"Refusing to overwrite existing non-mirror README: {path}\n"
            "Choose a dedicated output directory for the derived mirror."
        )
    path.write_text(text, encoding="utf-8")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _remove_if_present(path: Path) -> bool:
    if path.is_file():
        path.unlink()
        return True
    return False
def _iso_now() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
