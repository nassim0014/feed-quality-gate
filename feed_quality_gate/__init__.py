"""feed-quality-gate — validate, score and quarantine a tabular feed.

Typical use::

    from feed_quality_gate import gate, load_rules

    rules = load_rules("rules.yaml")
    report, clean, held = gate(df, rules)
    if not report.gate_passed:
        raise RuntimeError(report.to_json())
"""

from .gate import evaluate, gate
from .models import CheckResult, FeedReport, Severity
from .rules import Rules, RulesError, load_rules

__version__ = "0.1.0"

__all__ = [
    "evaluate",
    "gate",
    "load_rules",
    "Rules",
    "RulesError",
    "FeedReport",
    "CheckResult",
    "Severity",
    "__version__",
]
