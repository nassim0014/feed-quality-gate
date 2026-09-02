"""Synthetic fixtures.

Every row here is invented. No real feed, catalogue, competitor or customer
data is ever committed to this repository — the gate is generic by design and
its tests must stay that way.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from feed_quality_gate.rules import Rules

NOW = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)


def _feed(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


@pytest.fixture
def now() -> datetime:
    return NOW


@pytest.fixture
def rules() -> Rules:
    """A rule set mirroring rules.example.yaml, built in code for the tests."""
    return Rules.from_mapping(
        {
            "feed_id": "test-feed",
            "id_column": "product_id",
            "timestamp_column": "scraped_at",
            "freshness": {"max_age_days": 7, "severity": "fail"},
            "completeness": {
                "columns": {
                    "price": {
                        "max_null_ratio": 0.02,
                        "severity": "fail",
                        "quarantine": True,
                    },
                    "category": {
                        "max_null_ratio": 0.05,
                        "severity": "warn",
                        "quarantine": False,
                    },
                }
            },
        }
    )


@pytest.fixture
def clean_feed() -> pd.DataFrame:
    """Fresh, fully populated — should sail through the gate."""
    fresh = NOW - timedelta(hours=6)
    return _feed(
        [
            {
                "product_id": f"P{i:03d}",
                "price": 20.0 + i,
                "category": "oils",
                "scraped_at": fresh,
            }
            for i in range(50)
        ]
    )


@pytest.fixture
def stale_feed(clean_feed: pd.DataFrame) -> pd.DataFrame:
    """Perfectly complete, but frozen 33 days ago.

    Models the exact defect the gate was written for: nothing is wrong with any
    individual row, so every row-level check passes, and the feed is still
    worthless for a week-over-week comparison.
    """
    df = clean_feed.copy()
    df["scraped_at"] = NOW - timedelta(days=33)
    return df


@pytest.fixture
def holey_feed(clean_feed: pd.DataFrame) -> pd.DataFrame:
    """Fresh, but with missing prices expressed the way scrapers express them.

    Three rows have no usable price: one true null, one empty string, one
    whitespace. 3/50 = 6% > the 2% tolerance.
    """
    df = clean_feed.copy()
    df["price"] = df["price"].astype(object)
    df.loc[0, "price"] = None
    df.loc[1, "price"] = ""
    df.loc[2, "price"] = "   "
    return df
