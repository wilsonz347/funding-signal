"""
Silver-layer sanity checks for funding_rates (silver).

Confirms:
    - no duplicate keys (exchange, symbol, fetched_at)
    - silver is not falling behind bronze (catches a repeatedly failing
      silver job, e.g. a MERGE schema mismatch, before it goes unnoticed)
    - cast/quality issue rates are visible, not silently spiking
    - derived columns (rate_per_8h, rate_annualized) are actually being
      populated for rows where they should be computable

Run as a validation task depending on the silver transformation task.
"""

from datetime import datetime, timezone

BRONZE_TABLE = "funding_regime_project.bronze.raw_funding_rates"
SILVER_TABLE = "funding_regime_project.silver.funding_rates"

# Silver reads bronze on a 10-min cadence; alert if silver's latest poll
# is meaningfully behind bronze's latest poll.
MAX_LAG_MINUTES = 30


def _to_datetime(value):
    """
    Normalizes a fetched_at value to a timezone-aware datetime.
    Spark can return this as either a datetime or an ISO string
    depending on the driver path, so this handles both.
    """
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value


def check_silver_funding_rates(spark) -> dict:
    dup_row = spark.sql(f"""
        SELECT
            COUNT(*) AS rows,
            COUNT(DISTINCT CONCAT(exchange, symbol, fetched_at)) AS unique_keys
        FROM {SILVER_TABLE}
    """).collect()[0]

    lag_row = spark.sql(f"""
        SELECT
            (SELECT MAX(fetched_at) FROM {BRONZE_TABLE} WHERE base_coin = 'BTC') AS bronze_latest,
            (SELECT MAX(fetched_at) FROM {SILVER_TABLE}) AS silver_latest
    """).collect()[0]
    bronze_latest = _to_datetime(lag_row["bronze_latest"])
    silver_latest = _to_datetime(lag_row["silver_latest"])

    issue_row = spark.sql(f"""
        SELECT
            COUNT(*) AS rows,
            SUM(CASE WHEN silver_cast_issues != '[]' THEN 1 ELSE 0 END) AS cast_issue_rows,
            SUM(CASE WHEN silver_quality_issues != '[]' THEN 1 ELSE 0 END) AS quality_issue_rows
        FROM {SILVER_TABLE}
    """).collect()[0]

    # rate_per_8h should be non-null whenever rate and interval_hours are
    # both valid. A gap here is exactly the class of bug where the
    # derived-column computation silently stops running.
    derived_row = spark.sql(f"""
        SELECT
            COUNT(*) AS eligible_rows,
            SUM(CASE WHEN rate_per_8h IS NULL THEN 1 ELSE 0 END) AS null_rate_per_8h,
            SUM(CASE WHEN rate_annualized IS NULL THEN 1 ELSE 0 END) AS null_rate_annualized
        FROM {SILVER_TABLE}
        WHERE rate IS NOT NULL AND interval_hours IS NOT NULL AND interval_hours > 0
    """).collect()[0]

    result = {
        "rows": dup_row["rows"],
        "unique_keys": dup_row["unique_keys"],
        "bronze_latest": str(bronze_latest) if bronze_latest else None,
        "silver_latest": str(silver_latest) if silver_latest else None,
        "total_rows_checked": issue_row["rows"],
        "cast_issue_rows": issue_row["cast_issue_rows"],
        "quality_issue_rows": issue_row["quality_issue_rows"],
        "eligible_rows_for_normalization": derived_row["eligible_rows"],
        "null_rate_per_8h": derived_row["null_rate_per_8h"],
        "null_rate_annualized": derived_row["null_rate_annualized"],
    }

    if result["rows"] != result["unique_keys"]:
        raise ValueError(
            f"Duplicate keys detected in {SILVER_TABLE}: "
            f"{result['rows']} rows vs {result['unique_keys']} unique keys"
        )

    if bronze_latest is None or silver_latest is None:
        raise ValueError("Bronze or Silver has no data — cannot compute lag")

    lag_minutes = (bronze_latest - silver_latest).total_seconds() / 60
    result["lag_minutes"] = round(lag_minutes, 1)

    if lag_minutes > MAX_LAG_MINUTES:
        raise ValueError(
            f"Silver is falling behind Bronze by {lag_minutes:.1f} min "
            f"(threshold {MAX_LAG_MINUTES} min). Silver job may be failing "
            f"repeatedly (e.g. a MERGE schema mismatch)."
        )

    if derived_row["null_rate_per_8h"] > 0 or derived_row["null_rate_annualized"] > 0:
        raise ValueError(
            f"{derived_row['null_rate_per_8h']} rows have a null rate_per_8h and "
            f"{derived_row['null_rate_annualized']} have a null rate_annualized "
            f"despite valid rate/interval_hours. normalize_rate/annualize_rate "
            f"may not be wired into clean_row."
        )

    return result


if __name__ == "__main__":
    print(check_silver_funding_rates(spark))
