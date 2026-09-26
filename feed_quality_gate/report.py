"""Render a FeedReport for machines and for humans.

The JSON form is the contract: it is what price-bridge, an Airflow task, or the
loop-engine findings tooling should consume instead of re-deriving counts. The
console form exists so a person running the CLI can see what happened without
piping through `jq`.
"""

from __future__ import annotations

import math
from html import escape

from .models import FeedReport, Severity

_MARK = {True: "PASS", False: "FAIL"}

_SEVERITY_COLOR = {
    Severity.FAIL: "#dc2626",
    Severity.WARN: "#d97706",
    Severity.INFO: "#2563eb",
}
_PASS_COLOR = "#16a34a"
_GAUGE_RADIUS = 54
_GAUGE_CIRCUMFERENCE = 2 * math.pi * _GAUGE_RADIUS


def to_json(report: FeedReport, indent: int = 2) -> str:
    """The machine-readable form. Stable field names; see README."""
    return report.to_json(indent=indent)


def to_console(report: FeedReport) -> str:
    """A compact human summary, one line per check."""
    verdict = "PASSED" if report.gate_passed else "FAILED"
    lines = [
        f"feed:   {report.feed_id}",
        f"rows:   {report.row_count}",
        f"score:  {report.score}/100",
        f"gate:   {verdict}",
    ]

    if report.quarantined_ids:
        lines.append(f"held:   {len(report.quarantined_ids)} row(s) quarantined")

    lines.append("")
    for r in report.results:
        flag = _MARK[r.passed]
        sev = "" if r.passed else f" [{r.severity.value}]"
        lines.append(f"  {flag}{sev} {r.name}: {r.message}")
        if not r.passed and r.offending:
            sample = ", ".join(str(x) for x in r.offending)
            lines.append(f"         e.g. {sample}")

    return "\n".join(lines)


def to_markdown(report: FeedReport) -> str:
    """A Markdown table, for pasting into a findings file or a PR body."""
    verdict = "PASSED" if report.gate_passed else "FAILED"
    lines = [
        f"### Feed `{report.feed_id}` — {verdict} ({report.score}/100)",
        "",
        f"- rows: {report.row_count}",
        f"- quarantined: {len(report.quarantined_ids)}",
        f"- evaluated: {report.evaluated_at.isoformat()}",
        "",
        "| check | result | severity | detail |",
        "| --- | --- | --- | --- |",
    ]
    for r in report.results:
        sev = r.severity.value if not r.passed else "-"
        lines.append(f"| `{r.name}` | {_MARK[r.passed]} | {sev} | {r.message} |")
    return "\n".join(lines)


def to_html(report: FeedReport) -> str:
    """A single, dependency-free HTML page — for a viewer with no terminal.

    Everything is inlined (no external CSS/JS/fonts) so the file is safe to
    hand to `--html`, attach to a CI run, or open directly from disk. Every
    value taken from the feed or a check's message goes through `html.escape`
    first: a check's `message`/`offending` sample can contain arbitrary feed
    data, and this page must not become an XSS vector for whatever a scraper
    happened to pull in.
    """
    verdict = "PASSED" if report.gate_passed else "FAILED"
    verdict_color = _PASS_COLOR if report.gate_passed else _SEVERITY_COLOR[Severity.FAIL]
    dash = _GAUGE_CIRCUMFERENCE * report.score / 100

    rows = []
    for r in report.results:
        color = _PASS_COLOR if r.passed else _SEVERITY_COLOR[r.severity]
        sev = "-" if r.passed else r.severity.value
        detail = escape(r.message)
        if not r.passed and r.offending:
            sample = ", ".join(escape(str(x)) for x in r.offending)
            detail += f'<div class="offending">e.g. {sample}</div>'
        rows.append(
            "<tr>"
            f'<td><span class="badge" style="background:{color}">{_MARK[r.passed]}</span></td>'
            f"<td><code>{escape(r.name)}</code></td>"
            f"<td>{escape(sev)}</td>"
            f"<td>{detail}</td>"
            "</tr>"
        )

    quarantine_html = ""
    if report.quarantined_ids:
        shown = report.quarantined_ids[:20]
        sample = ", ".join(escape(str(x)) for x in shown)
        more = len(report.quarantined_ids) - len(shown)
        if more > 0:
            sample += f" (+{more} more)"
        quarantine_html = (
            f'<p class="quarantine">held back: {len(report.quarantined_ids)} row(s) — {sample}</p>'
        )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>fqg: {escape(report.feed_id)}</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{
    font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
    margin: 2rem auto; max-width: 720px; padding: 0 1rem;
    color: #1f2937; background: #ffffff;
  }}
  @media (prefers-color-scheme: dark) {{
    body {{ color: #e5e7eb; background: #111827; }}
    td {{ border-bottom-color: #374151 !important; }}
  }}
  .head {{ display: flex; align-items: center; gap: 1.5rem; }}
  h1 {{ font-size: 1.25rem; margin: 0; }}
  .sub {{ color: #6b7280; margin-top: .25rem; font-size: .9rem; }}
  .verdict {{ font-size: 1rem; font-weight: 700; color: {verdict_color}; margin-top: .25rem; }}
  .badge {{
    color: #fff; font-size: .75rem; font-weight: 600;
    padding: .15rem .5rem; border-radius: .25rem; white-space: nowrap;
  }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 1.5rem; }}
  td {{
    padding: .5rem .25rem; border-bottom: 1px solid #e5e7eb;
    vertical-align: top; font-size: .9rem;
  }}
  code {{ font-size: .85rem; }}
  .offending {{ color: #6b7280; font-size: .8rem; margin-top: .15rem; }}
  .quarantine {{ color: #92400e; }}
  .gauge-num {{ font: 700 1.4rem sans-serif; fill: currentColor; }}
</style>
</head>
<body>
  <div class="head">
    <svg width="96" height="96" viewBox="0 0 120 120"
         role="img" aria-label="score {report.score} of 100">
      <circle cx="60" cy="60" r="{_GAUGE_RADIUS}"
              fill="none" stroke="#e5e7eb" stroke-width="10"/>
      <circle cx="60" cy="60" r="{_GAUGE_RADIUS}"
              fill="none" stroke="{verdict_color}" stroke-width="10"
              stroke-dasharray="{dash:.1f} {_GAUGE_CIRCUMFERENCE:.1f}"
              stroke-linecap="round" transform="rotate(-90 60 60)"/>
      <text x="60" y="67" text-anchor="middle" class="gauge-num">{report.score}</text>
    </svg>
    <div>
      <h1>{escape(report.feed_id)}</h1>
      <div class="sub">
        {report.row_count} rows &middot; evaluated {escape(report.evaluated_at.isoformat())}
      </div>
      <div class="verdict">{verdict}</div>
    </div>
  </div>
  {quarantine_html}
  <table>
    <thead><tr><td><b>result</b></td><td><b>check</b></td><td><b>severity</b></td><td><b>detail</b></td></tr></thead>
    <tbody>{"".join(rows)}</tbody>
  </table>
</body>
</html>
"""


def exit_code(report: FeedReport) -> int:
    """0 when the gate passes, 1 when a FAIL-severity check failed.

    WARN-severity failures deliberately do not change the exit code — they
    lower the score and show up in the report, but they must not break a
    pipeline, or nobody will leave the gate switched on.
    """
    return 0 if report.gate_passed else 1


__all__ = ["to_json", "to_console", "to_markdown", "to_html", "exit_code", "Severity"]
