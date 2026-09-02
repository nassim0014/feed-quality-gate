"""Render a FeedReport for machines and for humans.

The JSON form is the contract: it is what price-bridge, an Airflow task, or the
loop-engine findings tooling should consume instead of re-deriving counts. The
console form exists so a person running the CLI can see what happened without
piping through `jq`.
"""

from __future__ import annotations

from .models import FeedReport, Severity

_MARK = {True: "PASS", False: "FAIL"}


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


def exit_code(report: FeedReport) -> int:
    """0 when the gate passes, 1 when a FAIL-severity check failed.

    WARN-severity failures deliberately do not change the exit code — they
    lower the score and show up in the report, but they must not break a
    pipeline, or nobody will leave the gate switched on.
    """
    return 0 if report.gate_passed else 1


__all__ = ["to_json", "to_console", "to_markdown", "exit_code", "Severity"]
