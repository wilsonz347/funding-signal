"""
Silver-layer quality checks.

find_quality_issues inspects a single record and returns a list of tags
for implausible values or cross-field inconsistencies.

All checks are row-level only.
"""

# Bound: catches unit/scale errors (e.g. 100x).
MAX_ABS_RATE = 0.05  # 5% per interval


def find_quality_issues(
    rate,
    interval_hours,
    mark_price,
    open_interest,
    fetched_at,
    updated_at,
    next_funding_time,
    age_seconds,
):
    issues = []

    if interval_hours is not None and interval_hours <= 0:
        issues.append("invalid_interval_hours")

    if age_seconds is not None and age_seconds <= 0:
        issues.append("invalid_age_seconds")

    if updated_at is not None and fetched_at is not None:
        if updated_at > fetched_at:
            issues.append("updated_at_after_fetched_at")

    if next_funding_time is not None and fetched_at is not None:
        if next_funding_time < fetched_at:
            issues.append("stale_next_funding_time")

    if next_funding_time is not None and updated_at is not None:
        if next_funding_time <= updated_at:
            issues.append("next_funding_time_not_after_updated_at")

    if mark_price is not None and mark_price <= 0:
        issues.append("invalid_mark_price")

    if open_interest is not None and open_interest < 0:
        issues.append("negative_open_interest")

    if rate is not None and abs(rate) > MAX_ABS_RATE:
        issues.append("implausible_rate_magnitude")

    return issues
