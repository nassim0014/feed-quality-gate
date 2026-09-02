"""Value objects for feed quality results.

Everything here is JSON-serialisable by design. The whole point of the gate is
to emit a machine-readable verdict that another process — price-bridge, an
Airflow task, or the loop-engine findings tooling — can consume without
re-parsing prose.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class Severity(StrEnum):
    """How much a failing check matters.

    INFO never affects the verdict, WARN lowers the score but still passes the
    gate, FAIL blocks. Str-valued so it serialises to JSON as its own name.
    """

    INFO = "info"
    WARN = "warn"
    FAIL = "fail"


#: Score penalty applied per failing check, by severity.
SEVERITY_WEIGHT: dict[Severity, int] = {
    Severity.INFO: 0,
    Severity.WARN: 10,
    Severity.FAIL: 30,
}


@dataclass
class CheckResult:
    """The outcome of one check over one feed.

    ``count``/``total`` are row counts where the check is row-oriented (e.g.
    completeness) and left at 0/0 where it is feed-oriented (e.g. freshness).
    ``offending`` is a *sample*, not the full set — the full set lives in
    ``FeedReport.quarantined_ids``.
    """

    name: str
    passed: bool
    severity: Severity = Severity.FAIL
    count: int = 0
    total: int = 0
    message: str = ""
    offending: list[Any] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def ratio(self) -> float:
        """Offending fraction, or 0.0 for feed-level checks with no row count."""
        return self.count / self.total if self.total else 0.0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["severity"] = self.severity.value
        d["ratio"] = round(self.ratio, 6)
        return d


@dataclass
class FeedReport:
    """Aggregate verdict over a feed.

    ``score`` is 100 minus the weighted penalties, floored at 0. It is a
    human-facing summary number; automation should branch on ``gate_passed``,
    which is driven purely by whether any FAIL-severity check failed.
    """

    feed_id: str
    evaluated_at: datetime
    row_count: int
    results: list[CheckResult] = field(default_factory=list)
    quarantined_ids: list[Any] = field(default_factory=list)

    @property
    def failures(self) -> list[CheckResult]:
        return [r for r in self.results if not r.passed]

    @property
    def score(self) -> int:
        penalty = sum(SEVERITY_WEIGHT[r.severity] for r in self.failures)
        return max(0, 100 - penalty)

    @property
    def gate_passed(self) -> bool:
        return not any(
            r.severity is Severity.FAIL for r in self.failures
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "feed_id": self.feed_id,
            "evaluated_at": self.evaluated_at.astimezone(UTC).isoformat(),
            "row_count": self.row_count,
            "score": self.score,
            "gate_passed": self.gate_passed,
            "quarantined_count": len(self.quarantined_ids),
            "quarantined_ids": self.quarantined_ids,
            "results": [r.to_dict() for r in self.results],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)
