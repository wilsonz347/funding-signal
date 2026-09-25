"""
Tests for find_quality_issues (src/transformations/quality_checks.py).

Row-level checks only. Returns a list of issue tags; empty list = clean.
"""

from datetime import datetime, timezone

from src.transformations.quality_checks import find_quality_issues


GOOD_VALUES = {
    "rate": 0.0001,
    "interval_hours": 8,
    "mark_price": 77381.9,
    "open_interest": 8_408_566_417.0,
    "fetched_at": datetime(2026, 9, 18, 3, 36, tzinfo=timezone.utc),
    "updated_at": datetime(2026, 9, 18, 3, 35, tzinfo=timezone.utc),
    "next_funding_time": datetime(2026, 9, 18, 8, 0, tzinfo=timezone.utc),
    "age_seconds": 23,
}


def test_good_row_has_no_quality_issues():
    issues = find_quality_issues(**GOOD_VALUES)

    assert issues == []


def test_invalid_interval_hours():
    values = dict(GOOD_VALUES)
    values["interval_hours"] = 0

    issues = find_quality_issues(**values)

    assert "invalid_interval_hours" in issues


def test_negative_age_seconds():
    values = dict(GOOD_VALUES)
    values["age_seconds"] = -1

    issues = find_quality_issues(**values)

    assert "invalid_age_seconds" in issues


def test_updated_at_after_fetched_at():
    values = dict(GOOD_VALUES)
    values["updated_at"] = datetime(
        2026, 9, 18, 3, 37, tzinfo=timezone.utc
    )

    issues = find_quality_issues(**values)

    assert "updated_at_after_fetched_at" in issues


def test_next_funding_time_before_fetched_at():
    values = dict(GOOD_VALUES)
    values["next_funding_time"] = datetime(
        2026, 9, 18, 3, 35, tzinfo=timezone.utc
    )

    issues = find_quality_issues(**values)

    assert "stale_next_funding_time" in issues


def test_next_funding_time_not_after_updated_at():
    values = dict(GOOD_VALUES)
    values["next_funding_time"] = values["updated_at"]

    issues = find_quality_issues(**values)

    assert "next_funding_time_not_after_updated_at" in issues


def test_invalid_mark_price():
    values = dict(GOOD_VALUES)
    values["mark_price"] = 0

    issues = find_quality_issues(**values)

    assert "invalid_mark_price" in issues


def test_negative_open_interest():
    values = dict(GOOD_VALUES)
    values["open_interest"] = -1

    issues = find_quality_issues(**values)

    assert "negative_open_interest" in issues


def test_implausible_rate():
    values = dict(GOOD_VALUES)
    values["rate"] = 0.1

    issues = find_quality_issues(**values)

    assert "implausible_rate_magnitude" in issues
