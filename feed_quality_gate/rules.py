"""Declarative rule configuration.

Rules are data, not code. A new feed is onboarded by writing a YAML file, not
by editing this package — that is what makes the gate reusable across the
scraped-price feed, an accounting extract, or anything else tabular.

No feed schema is hardcoded anywhere in this repo. Column names always come
from the rules file.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, ValidationError

from .models import Severity


class FreshnessRule(BaseModel):
    """Fail when the newest row in the feed is older than ``max_age_days``."""

    enabled: bool = True
    max_age_days: float = Field(default=7.0, gt=0)
    severity: Severity = Severity.FAIL


class ColumnRule(BaseModel):
    """Per-column tolerance for missing values.

    ``max_null_ratio`` is a fraction of rows, so 0.02 means "at most 2% of rows
    may be missing this column".
    """

    max_null_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    severity: Severity = Severity.FAIL
    quarantine: bool = True


class CompletenessRule(BaseModel):
    """Which columns must be populated, and how tolerant to be about each."""

    enabled: bool = True
    columns: dict[str, ColumnRule] = Field(default_factory=dict)


class Rules(BaseModel):
    """A complete rule set for one feed."""

    feed_id: str = "unnamed-feed"
    id_column: str | None = None
    timestamp_column: str | None = None
    freshness: FreshnessRule = Field(default_factory=FreshnessRule)
    completeness: CompletenessRule = Field(default_factory=CompletenessRule)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> Rules:
        return cls.model_validate(data)


class RulesError(ValueError):
    """Raised with a readable message instead of a raw pydantic traceback.

    Mirrors the approach analytics-service-toolkit takes in ``load_settings``:
    a config mistake should read like a sentence, not a stack trace.
    """


def load_rules(path: str | Path) -> Rules:
    """Load and validate a rules YAML file."""
    p = Path(path)
    if not p.is_file():
        raise RulesError(f"rules file not found: {p}")

    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise RulesError(f"{p} is not valid YAML: {exc}") from exc

    if not isinstance(raw, dict):
        raise RulesError(f"{p} must contain a YAML mapping at the top level")

    try:
        return Rules.from_mapping(raw)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(x) for x in e['loc']) or '<root>'}: {e['msg']}"
            for e in exc.errors()
        )
        raise RulesError(f"invalid rules in {p} — {problems}") from exc
