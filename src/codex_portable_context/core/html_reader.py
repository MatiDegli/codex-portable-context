"""Static HTML reader rendering for derived mirrors."""

from __future__ import annotations

import html
from typing import Any

from .markdown import pretty_timestamp


def render_reader_index(
    *,
    entries: list[dict[str, Any]],
    exported_at: str,
    redacted_export: bool,
) -> str:
    """Render a self-contained HTML landing page for the derived mirror."""

    cards = "\n".join(_render_index_card(entry) for entry in entries) or (
        '<p class="empty">No sessions are currently exported in this mirror.</p>'
    )
    latest = entries[0] if entries else None
    latest_updated = pretty_timestamp(_entry_sort_timestamp(latest) if latest else None)
    latest_link = (
        f'<a class="primary-link" href="{_escape_attr(str(latest.get("reader_relpath") or ""))}">'
        "Open latest session reader</a>"
        if latest
        else ""
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Codex Portable Context Mirror</title>
  <style>
    :root {{
      color-scheme: light dark;
      --bg: #f4f1ea;
      --panel: rgba(255, 252, 246, 0.92);
      --border: #c9bda8;
      --text: #211c16;
      --muted: #65594b;
      --accent: #8a4b08;
      --accent-soft: rgba(138, 75, 8, 0.1);
      --shadow: 0 18px 40px rgba(58, 40, 22, 0.08);
      --mono: "Iosevka", "JetBrains Mono", "Cascadia Mono", monospace;
      --sans: "IBM Plex Sans", "Segoe UI", sans-serif;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg: #161311;
        --panel: rgba(31, 27, 23, 0.94);
        --border: #4f4337;
        --text: #efe6da;
        --muted: #bcae9d;
        --accent: #f3a14d;
        --accent-soft: rgba(243, 161, 77, 0.14);
        --shadow: 0 18px 40px rgba(0, 0, 0, 0.35);
      }}
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: var(--sans);
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(138, 75, 8, 0.12), transparent 32%),
        linear-gradient(180deg, var(--bg), color-mix(in srgb, var(--bg) 78%, black 6%));
      min-height: 100vh;
    }}
    main {{
      max-width: 1080px;
      margin: 0 auto;
      padding: 40px 20px 64px;
    }}
    .hero, .card {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 20px;
      box-shadow: var(--shadow);
    }}
    .hero {{
      padding: 28px;
      margin-bottom: 24px;
    }}
    h1, h2, h3 {{
      margin: 0;
      line-height: 1.15;
    }}
    h1 {{
      font-size: clamp(2rem, 5vw, 3rem);
      letter-spacing: -0.03em;
    }}
    h2 {{
      font-size: 1.15rem;
      color: var(--muted);
      margin-top: 6px;
      font-weight: 600;
    }}
    p, li {{ line-height: 1.6; }}
    .summary-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin: 20px 0 18px;
    }}
    .summary-item {{
      padding: 14px 16px;
      border-radius: 16px;
      background: var(--accent-soft);
      border: 1px solid color-mix(in srgb, var(--border) 75%, var(--accent) 25%);
    }}
    .summary-label {{
      display: block;
      font-size: 0.8rem;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 6px;
    }}
    .summary-value {{
      font-size: 1rem;
      font-weight: 700;
    }}
    .links {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-top: 18px;
    }}
    a {{
      color: var(--accent);
      text-decoration-thickness: 1.5px;
      text-underline-offset: 0.18em;
    }}
    .primary-link {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 10px 16px;
      border-radius: 999px;
      background: var(--accent);
      color: white;
      text-decoration: none;
      font-weight: 700;
    }}
    .toolbar {{
      display: flex;
      gap: 12px;
      align-items: center;
      justify-content: space-between;
      margin: 18px 0 14px;
      flex-wrap: wrap;
    }}
    .toolbar input {{
      width: min(100%, 340px);
      padding: 12px 14px;
      border-radius: 12px;
      border: 1px solid var(--border);
      background: var(--panel);
      color: var(--text);
      font: inherit;
    }}
    .cards {{
      display: grid;
      gap: 16px;
    }}
    .card {{
      padding: 20px;
    }}
    .meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px 14px;
      margin: 10px 0 14px;
      color: var(--muted);
      font-size: 0.95rem;
    }}
    .badge {{
      display: inline-block;
      padding: 4px 10px;
      border-radius: 999px;
      font-size: 0.78rem;
      font-weight: 700;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      background: var(--accent-soft);
      color: var(--accent);
    }}
    .badge-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 14px;
    }}
    .detail {{
      margin: 8px 0 0;
    }}
    .label {{
      font-weight: 700;
      color: var(--muted);
      margin-right: 8px;
    }}
    code {{
      font-family: var(--mono);
      font-size: 0.94em;
    }}
    .empty {{
      padding: 24px;
      border: 1px dashed var(--border);
      border-radius: 16px;
      color: var(--muted);
      background: var(--panel);
    }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <h1>Codex Portable Context Mirror</h1>
      <h2>Static reader for a derived, read-only Codex mirror</h2>
      <p>
        This interface is generated from the derived mirror only. It does not
        write back into Codex and it is safe to move with the mirror as a
        self-contained reading layer.
      </p>
      <div class="summary-grid">
        <div class="summary-item">
          <span class="summary-label">Sessions</span>
          <span class="summary-value">{len(entries)}</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">Exported At</span>
          <span class="summary-value">{_escape_text(pretty_timestamp(exported_at))}</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">Latest Update</span>
          <span class="summary-value">{_escape_text(latest_updated)}</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">Redacted</span>
          <span class="summary-value">{"yes" if redacted_export else "no"}</span>
        </div>
      </div>
      <div class="badge-row">
        <span class="badge">{"Redacted export" if redacted_export else "Standard export"}</span>
        <span class="badge">Static reader</span>
      </div>
      <div class="links">
        {latest_link}
        <a href="README.md">Open mirror README</a>
        <a href="sessions-index.jsonl">Open sessions-index.jsonl</a>
      </div>
    </section>
    <div class="toolbar">
      <div>
        <strong>Sessions</strong><br>
        <span style="color: var(--muted);">
          Filter by title, id, preview, activity, or environment.
        </span>
      </div>
      <input id="session-filter" type="search" placeholder="Filter sessions...">
    </div>
    <section class="cards" id="session-list">
      {cards}
    </section>
  </main>
  <script>
    const input = document.getElementById("session-filter");
    const cards = Array.from(document.querySelectorAll("[data-filter]"));
    input?.addEventListener("input", () => {{
      const query = input.value.trim().toLowerCase();
      for (const card of cards) {{
        const haystack = card.getAttribute("data-filter") || "";
        card.style.display = !query || haystack.includes(query) ? "" : "none";
      }}
    }});
  </script>
</body>
</html>
"""


def render_session_reader(
    *,
    entry: dict[str, Any],
    metadata_text: str,
    markdown_text: str,
) -> str:
    """Render a self-contained HTML reader page for one session."""

    session_id = str(entry.get("session_id") or "")
    title = str(entry.get("title") or f"Session {session_id}")
    summary = entry.get("summary")
    summary_dict = summary if isinstance(summary, dict) else {}
    export_status = "Redacted export" if entry.get("redacted") else "Standard export"
    export_profile = _escape_text(str(entry.get("export_profile") or "unknown profile"))
    transcript_rel = "../" + str(entry.get("markdown_relpath") or f"sessions/{session_id}.md")
    metadata_rel = "../" + str(entry.get("metadata_relpath") or f"metadata/{session_id}.json")
    handoff_markdown_rel = f"../handoffs/{session_id}.md"
    handoff_json_rel = f"../handoffs/{session_id}.json"

    metadata_rows = [
        ("Session ID", session_id),
        ("Updated", pretty_timestamp(_entry_sort_timestamp(entry))),
        ("Session Timestamp", pretty_timestamp(_optional_string(entry.get("session_timestamp")))),
        ("Thread Name", _optional_string(entry.get("thread_name"))),
        ("CWD", _optional_string(entry.get("cwd"))),
        ("Originator", _optional_string(entry.get("originator"))),
        ("Source", _optional_string(entry.get("source"))),
        ("Model Provider", _optional_string(entry.get("model_provider"))),
        ("CLI Version", _optional_string(entry.get("cli_version"))),
        ("Export Profile", _optional_string(entry.get("export_profile"))),
        ("Redacted", "yes" if entry.get("redacted") else "no"),
    ]
    metadata_rows_html = "\n".join(
        f"<tr><th>{_escape_text(label)}</th><td>{_escape_text(value)}</td></tr>"
        for label, value in metadata_rows
        if value
    )

    detail_blocks = []
    if summary_dict.get("preview"):
        detail_blocks.append(_detail_block("Started with", str(summary_dict["preview"])))
    if summary_dict.get("last_assistant_message"):
        detail_blocks.append(
            _detail_block("Latest assistant reply", str(summary_dict["last_assistant_message"]))
        )
    if summary_dict.get("activity"):
        detail_blocks.append(_detail_block("Activity", str(summary_dict["activity"])))
    if summary_dict.get("environment"):
        detail_blocks.append(_detail_block("Environment", str(summary_dict["environment"])))

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_escape_text(title)} | Codex Portable Context</title>
  <style>
    :root {{
      color-scheme: light dark;
      --bg: #f7f2ea;
      --panel: rgba(255, 252, 247, 0.94);
      --border: #c9baa0;
      --text: #221c16;
      --muted: #6f6254;
      --accent: #9a4f16;
      --accent-soft: rgba(154, 79, 22, 0.1);
      --shadow: 0 20px 40px rgba(47, 32, 18, 0.1);
      --mono: "Iosevka", "JetBrains Mono", "Cascadia Mono", monospace;
      --sans: "IBM Plex Sans", "Segoe UI", sans-serif;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg: #171311;
        --panel: rgba(30, 25, 22, 0.96);
        --border: #53473a;
        --text: #f0e6db;
        --muted: #bfaf9d;
        --accent: #f3a14d;
        --accent-soft: rgba(243, 161, 77, 0.14);
        --shadow: 0 20px 44px rgba(0, 0, 0, 0.34);
      }}
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--text);
      font-family: var(--sans);
      background:
        radial-gradient(circle at top right, rgba(154, 79, 22, 0.12), transparent 28%),
        linear-gradient(180deg, var(--bg), color-mix(in srgb, var(--bg) 78%, black 7%));
    }}
    main {{
      max-width: 1200px;
      margin: 0 auto;
      padding: 32px 18px 60px;
    }}
    .hero, .panel {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 20px;
      box-shadow: var(--shadow);
    }}
    .hero {{
      padding: 24px;
      margin-bottom: 20px;
    }}
    h1 {{
      margin: 0;
      font-size: clamp(1.8rem, 4vw, 2.8rem);
      line-height: 1.1;
      letter-spacing: -0.03em;
    }}
    .sub {{
      color: var(--muted);
      margin-top: 8px;
      line-height: 1.6;
    }}
    .links {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-top: 16px;
    }}
    a {{
      color: var(--accent);
      text-decoration-thickness: 1.5px;
      text-underline-offset: 0.18em;
    }}
    .primary-link {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 10px 16px;
      border-radius: 999px;
      background: var(--accent);
      color: white;
      text-decoration: none;
      font-weight: 700;
    }}
    .subnav {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 14px;
    }}
    .layout {{
      display: grid;
      grid-template-columns: minmax(280px, 340px) minmax(0, 1fr);
      gap: 18px;
      align-items: start;
    }}
    @media (max-width: 900px) {{
      .layout {{ grid-template-columns: 1fr; }}
    }}
    .panel {{
      padding: 18px 20px;
    }}
    h2 {{
      margin: 0 0 14px;
      font-size: 1.05rem;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.95rem;
    }}
    th, td {{
      text-align: left;
      padding: 9px 0;
      border-bottom: 1px solid color-mix(in srgb, var(--border) 78%, transparent);
      vertical-align: top;
    }}
    th {{
      color: var(--muted);
      width: 42%;
      font-weight: 700;
    }}
    .detail {{
      margin: 0 0 14px;
      line-height: 1.6;
    }}
    .detail strong {{
      color: var(--muted);
      display: block;
      margin-bottom: 4px;
      font-size: 0.86rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    .note {{
      color: var(--muted);
      font-size: 0.94rem;
      line-height: 1.55;
    }}
    .badge {{
      display: inline-block;
      padding: 4px 10px;
      border-radius: 999px;
      font-size: 0.78rem;
      font-weight: 700;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      background: var(--accent-soft);
      color: var(--accent);
    }}
    .badge-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 14px;
    }}
    pre {{
      margin: 0;
      padding: 18px;
      border-radius: 16px;
      overflow: auto;
      font: 0.95rem/1.55 var(--mono);
      background: color-mix(in srgb, var(--panel) 92%, black 8%);
      border: 1px solid color-mix(in srgb, var(--border) 72%, transparent);
      white-space: pre-wrap;
      word-break: break-word;
    }}
    details {{
      margin-top: 16px;
    }}
    summary {{
      cursor: pointer;
      color: var(--muted);
      font-weight: 700;
    }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <h1>{_escape_text(title)}</h1>
      <p class="sub">
        Static reader view generated from the derived mirror. This page is safe
        to move with the mirror and does not depend on the original Codex
        source logs.
      </p>
      <div class="badge-row">
        <span class="badge">{export_status}</span>
        <span class="badge">{export_profile}</span>
      </div>
      <div class="links">
        <a class="primary-link" href="../index.html">Back to reader index</a>
        <a href="../README.md">Mirror README</a>
        <a href="{_escape_attr(transcript_rel)}">Raw transcript Markdown</a>
        <a href="{_escape_attr(metadata_rel)}">Metadata JSON</a>
        <a href="{_escape_attr(handoff_markdown_rel)}">Handoff Markdown</a>
        <a href="{_escape_attr(handoff_json_rel)}">Handoff JSON</a>
      </div>
      <nav class="subnav" aria-label="Session sections">
        <a href="#snapshot">Jump to snapshot</a>
        <a href="#metadata">Jump to metadata</a>
        <a href="#handoff">Jump to handoff</a>
        <a href="#transcript">Jump to transcript</a>
        <a href="#raw-metadata">Jump to raw metadata</a>
      </nav>
    </section>
    <section class="layout">
      <aside class="panel" id="snapshot">
        <h2>Session Snapshot</h2>
        {"".join(detail_blocks) or '<p class="detail">No summary details available.</p>'}
        <div id="metadata"></div>
        <h2>Metadata</h2>
        <table>{metadata_rows_html}</table>
        <div id="handoff"></div>
        <h2>Handoff</h2>
        <div class="detail">
          <strong>Bundle paths</strong>
          <a href="{_escape_attr(handoff_markdown_rel)}">Markdown handoff</a><br>
          <a href="{_escape_attr(handoff_json_rel)}">JSON handoff</a>
        </div>
        <p class="note">
          If the handoff bundle has not been generated yet, create it with
          <code>codex-session-handoff {session_id[:8]}</code> or
          <code>codex-session-handoff --latest</code>.
        </p>
      </aside>
      <section class="panel" id="transcript">
        <h2>Transcript</h2>
        <pre>{_escape_text(markdown_text)}</pre>
        <details id="raw-metadata">
          <summary>Show raw metadata JSON</summary>
          <pre>{_escape_text(metadata_text)}</pre>
        </details>
      </section>
    </section>
  </main>
</body>
</html>
"""


def _render_index_card(entry: dict[str, Any]) -> str:
    summary = entry.get("summary")
    summary_dict = summary if isinstance(summary, dict) else {}
    session_id = str(entry.get("session_id") or "")
    title = str(entry.get("title") or f"Session {session_id}")
    filter_parts = [
        session_id,
        title,
        str(summary_dict.get("preview") or ""),
        str(summary_dict.get("activity") or ""),
        str(summary_dict.get("environment") or ""),
    ]
    filters = _escape_attr(" ".join(part.lower() for part in filter_parts if part))
    reader_relpath = str(entry.get("reader_relpath") or "")
    markdown_relpath = str(entry.get("markdown_relpath") or "")
    metadata_relpath = str(entry.get("metadata_relpath") or "")
    handoff_relpath = f"handoffs/{session_id}.md"
    badges = []
    if entry.get("redacted"):
        badges.append('<span class="badge">Redacted</span>')
    export_profile = entry.get("export_profile")
    if export_profile:
        badges.append(f'<span class="badge">{_escape_text(str(export_profile))}</span>')
    badge_html = " ".join(badges)

    details = []
    if summary_dict.get("preview"):
        details.append(_card_line("Started with", str(summary_dict["preview"])))
    if summary_dict.get("activity"):
        details.append(_card_line("Activity", str(summary_dict["activity"])))
    if summary_dict.get("environment"):
        details.append(_card_line("Environment", str(summary_dict["environment"])))

    return (
        f'<article class="card" data-filter="{filters}">'
        f"<h3>{_escape_text(title)}</h3>"
        f'<div class="meta"><span><code>{_escape_text(session_id)}</code></span>'
        f"<span>{_escape_text(pretty_timestamp(_entry_sort_timestamp(entry)))}</span>"
        f"{badge_html}</div>"
        f"{''.join(details)}"
        '<div class="links">'
        f'<a class="primary-link" href="{_escape_attr(reader_relpath)}">Open reader</a>'
        f'<a href="{_escape_attr(markdown_relpath)}">Transcript Markdown</a>'
        f'<a href="{_escape_attr(metadata_relpath)}">Metadata JSON</a>'
        f'<a href="{_escape_attr(handoff_relpath)}">Handoff bundle</a>'
        "</div>"
        "</article>"
    )


def _card_line(label: str, value: str) -> str:
    return (
        '<p class="detail">'
        f'<span class="label">{_escape_text(label)}:</span>{_escape_text(value)}'
        "</p>"
    )


def _detail_block(label: str, value: str) -> str:
    return (
        '<div class="detail">'
        f"<strong>{_escape_text(label)}</strong>"
        f"{_escape_text(value)}"
        "</div>"
    )


def _entry_sort_timestamp(entry: dict[str, Any] | None) -> str | None:
    if not entry:
        return None
    for key in ("updated_at", "session_timestamp", "exported_at"):
        value = entry.get(key)
        if value:
            return str(value)
    return None


def _optional_string(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    return text if text.strip() else ""


def _escape_text(value: str) -> str:
    return html.escape(value, quote=False)


def _escape_attr(value: str) -> str:
    return html.escape(value, quote=True)
