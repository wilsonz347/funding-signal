"""
Tests for compute_poll_lag_seconds (src/transformations/silver_transform.py).
"""

from datetime import datetime, timezone
from src.transformations.silver_transform import compute_poll_lag_seconds

def test_poll_lag_seconds():
    fetched_at = datetime(2026, 9, 18, 3, 40, tzinfo=timezone.utc)
    updated_at = datetime(2026, 9, 18, 3, 39, tzinfo=timezone.utc)

    assert compute_poll_lag_seconds(fetched_at, updated_at) == 60


def test_poll_lag_returns_negative_when_updated_after_fetched():
    fetched_at = datetime(2026, 9, 18, 3, 39, tzinfo=timezone.utc)
    updated_at = datetime(2026, 9, 18, 3, 40, tzinfo=timezone.utc)

    assert compute_poll_lag_seconds(fetched_at, updated_at) == -60


def test_poll_lag_returns_none_when_timestamp_missing():
    fetched_at = datetime(2026, 9, 18, 3, 40, tzinfo=timezone.utc)

    assert compute_poll_lag_seconds(fetched_at, None) is None
    assert compute_poll_lag_seconds(None, fetched_at) is None
