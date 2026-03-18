"""Pure-Python read-only bridge helpers for derived mirror operations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from codex_portable_context.core.discovery import default_out_dir, mirror_layout
from codex_portable_context.core.handoff import generate_handoff
from codex_portable_context.core.index import (
    entry_path,
    entry_session_id,
    entry_title,
    latest_entry,
    load_index,
)
from codex_portable_context.core.listing import ListOptions, enrich_entry, filter_entries
from codex_portable_context.core.resolve import resolve_unique_entry

BridgePayload = dict[str, Any]


class MirrorBridge:
    """Small read-only wrapper around the existing derived-mirror core helpers."""

    def __init__(self, out_dir: Path | None = None) -> None:
        self.out_dir = (out_dir or default_out_dir()).expanduser().resolve()

    def session_list(
        self,
        *,
        limit: int = 0,
        title_filter: str = "",
        id_filter: str = "",
    ) -> BridgePayload:
        """Return filtered mirror sessions with absolute artifact paths."""

        entries = load_index(self.out_dir)
        filtered = filter_entries(
            entries,
            ListOptions(limit=limit, title_filter=title_filter, id_filter=id_filter),
        )
        items = [self._list_item(entry) for entry in filtered]
        return {
            "operation": "session_list",
            "out_dir": str(self.out_dir),
            "count": len(items),
            "sessions": items,
        }

    def get_latest_session_summary(self) -> BridgePayload:
        """Return the latest exported session with summary-focused fields."""

        entry = self._require_latest_entry()
        return {
            "operation": "get_latest_session_summary",
            "out_dir": str(self.out_dir),
            "session": self._list_item(entry),
        }

    def session_artifacts_get(
        self,
        *,
        session_id: str | None = None,
        selector: str | None = None,
        latest: bool = False,
        include_handoff_paths: bool = True,
    ) -> BridgePayload:
        """Return the artifact bundle for one derived mirror session."""

        entry = self._resolve_entry(session_id=session_id, selector=selector, latest=latest)
        return {
            "operation": "session_artifacts_get",
            "out_dir": str(self.out_dir),
            "artifact": self._artifact_bundle(
                entry,
                include_handoff_paths=include_handoff_paths,
            ),
        }

    def session_handoff_get(
        self,
        *,
        session_id: str | None = None,
        selector: str | None = None,
        latest: bool = False,
    ) -> BridgePayload:
        """Generate or refresh one handoff bundle and return absolute artifact paths."""

        entry = self._resolve_entry(session_id=session_id, selector=selector, latest=latest)
        result = generate_handoff(entry, self.out_dir)
        handoff_payload = json.loads(result.json_path.read_text(encoding="utf-8"))
        artifact = self._artifact_bundle(entry, include_handoff_paths=True)
        return {
            "operation": "session_handoff_get",
            "out_dir": str(self.out_dir),
            "session_id": str(entry["session_id"]),
            "title": artifact["title"],
            "redacted": artifact["redacted"],
            "handoff_markdown_path": str(result.markdown_path.resolve()),
            "handoff_json_path": str(result.json_path.resolve()),
            "handoff_markdown_relpath": artifact["relpaths"]["handoff_markdown_relpath"],
            "handoff_json_relpath": artifact["relpaths"]["handoff_json_relpath"],
            "source_available": bool(
                handoff_payload.get("source_availability", {}).get("source_available", False)
            ),
            "artifact": artifact,
            "handoff": handoff_payload,
            "paths": {
                "markdown": str(result.markdown_path.resolve()),
                "json": str(result.json_path.resolve()),
                "metadata": artifact["paths"]["metadata_path"],
                "session_markdown": artifact["paths"]["markdown_path"],
                "reader": artifact["paths"]["reader_path"],
            },
        }

    def _require_latest_entry(self) -> dict[str, Any]:
        entries = load_index(self.out_dir)
        entry = latest_entry(entries)
        if entry is None:
            raise ValueError(f"No exported sessions are available in {self.out_dir}")
        return entry

    def _resolve_entry(
        self,
        *,
        session_id: str | None = None,
        selector: str | None = None,
        latest: bool = False,
    ) -> dict[str, Any]:
        selection_count = sum(
            1 for mode in (bool(session_id), bool(selector), latest) if mode
        )
        if selection_count != 1:
            raise ValueError(
                "Choose exactly one selection mode: session_id, selector, or latest=True."
            )

        entries = load_index(self.out_dir)
        if latest:
            entry = latest_entry(entries)
            if entry is None:
                raise ValueError(f"No exported sessions are available in {self.out_dir}")
            return entry

        if session_id:
            for entry in entries:
                if entry_session_id(entry) == session_id:
                    return entry
            raise ValueError(f"No exported session matched session_id: {session_id}")

        assert selector is not None
        return resolve_unique_entry(entries, selector)

    def _list_item(self, entry: dict[str, Any]) -> BridgePayload:
        item = dict(enrich_entry(entry))
        item["paths"] = {
            "metadata": self._path_string(entry, "metadata"),
            "session_markdown": self._path_string(entry, "markdown"),
            "reader": self._path_string(entry, "reader"),
            "handoff_markdown": self._path_string(entry, "handoff"),
        }
        return item

    def _artifact_bundle(
        self,
        entry: dict[str, Any],
        *,
        include_handoff_paths: bool,
    ) -> BridgePayload:
        enriched = enrich_entry(entry)
        metadata_path = entry_path(entry, "metadata", self.out_dir).resolve()
        markdown_path = entry_path(entry, "markdown", self.out_dir).resolve()
        reader_path = entry_path(entry, "reader", self.out_dir).resolve()
        if not metadata_path.is_file():
            raise FileNotFoundError(f"Mirror metadata artifact missing: {metadata_path}")
        if not markdown_path.is_file():
            raise FileNotFoundError(f"Mirror transcript artifact missing: {markdown_path}")

        layout = mirror_layout(self.out_dir)
        session_id = entry_session_id(entry)
        relpaths: BridgePayload = {
            "metadata_relpath": str(enriched["metadata_relpath"]),
            "markdown_relpath": str(enriched["markdown_relpath"]),
            "reader_relpath": str(entry.get("reader_relpath") or layout.reader_relpath(session_id)),
        }
        paths: BridgePayload = {
            "landing_path": str(layout.landing_path.resolve()),
            "reader_index_path": str(layout.reader_index_path.resolve()),
            "metadata_path": str(metadata_path),
            "markdown_path": str(markdown_path),
            "reader_path": str(reader_path),
        }
        if include_handoff_paths:
            relpaths["handoff_markdown_relpath"] = str(layout.handoff_markdown_relpath(session_id))
            relpaths["handoff_json_relpath"] = str(layout.handoff_json_relpath(session_id))
            paths["handoff_markdown_path"] = str(layout.handoff_markdown_path(session_id).resolve())
            paths["handoff_json_path"] = str(layout.handoff_json_path(session_id).resolve())

        artifact: BridgePayload = {
            "provider": str(entry.get("provider") or "codex"),
            "session_id": session_id,
            "title": entry_title(entry),
            "redacted": bool(entry.get("redacted", False)),
            "summary": dict(entry.get("summary") or {}),
            "paths": paths,
            "relpaths": relpaths,
        }
        for key in ("updated_at", "exported_at", "export_profile", "redaction_report"):
            value = entry.get(key)
            if value not in (None, ""):
                artifact[key] = value
        return artifact

    def _path_string(self, entry: dict[str, Any], kind: str) -> str:
        return str(entry_path(entry, kind, self.out_dir).resolve())


def session_list(
    *,
    out_dir: Path | None = None,
    limit: int = 0,
    title_filter: str = "",
    id_filter: str = "",
) -> BridgePayload:
    """Return the derived session listing for MCP-facing callers."""

    return MirrorBridge(out_dir).session_list(
        limit=limit,
        title_filter=title_filter,
        id_filter=id_filter,
    )


def get_latest_session_summary(*, out_dir: Path | None = None) -> BridgePayload:
    """Return the latest derived session summary for MCP-facing callers."""

    return MirrorBridge(out_dir).get_latest_session_summary()


def session_artifacts_get(
    *,
    out_dir: Path | None = None,
    session_id: str | None = None,
    selector: str | None = None,
    latest: bool = False,
    include_handoff_paths: bool = True,
) -> BridgePayload:
    """Return the artifact bundle for one derived session."""

    return MirrorBridge(out_dir).session_artifacts_get(
        session_id=session_id,
        selector=selector,
        latest=latest,
        include_handoff_paths=include_handoff_paths,
    )


def session_handoff_get(
    *,
    out_dir: Path | None = None,
    session_id: str | None = None,
    selector: str | None = None,
    latest: bool = False,
) -> BridgePayload:
    """Return one generated handoff bundle for MCP-facing callers."""

    return MirrorBridge(out_dir).session_handoff_get(
        session_id=session_id,
        selector=selector,
        latest=latest,
    )
