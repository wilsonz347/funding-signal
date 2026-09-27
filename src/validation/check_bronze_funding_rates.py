"""
Bronze-layer sanity checks for funding_rates (bronze).

Confirms:
    - no duplicate keys (exchange, symbol, fetched_at)
    - the latest poll has a full set of contracts (no partial fetch)
    - bronze is fresh (the ingestion job is running on schedule)
    - schema drift is visible and not silently growing unnoticed

Run as a validation task depending on the bronze ingestion task.
"""

from datetime import datetime, timezone

BRONZE_TABLE = "funding_regime_project.bronze.raw_funding_rates"

# Expect ~42 BTC contracts per poll. Set generously below the true count
# so a couple of missing venues doesn't false-alarm; adjust as coverage changes.
MIN_EXPECTED_CONTRACTS_PER_POLL = 35

# Bronze polls every 10 minutes; alert if the latest row is older than this.
MAX_FRESHNESS_MINUTES = 30


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


def check_bronze_funding_rates(spark) -> dict:
    dup_row = spark.sql(f"""
        SELECT
            COUNT(*) AS rows,
            COUNT(DISTINCT CONCAT(exchange, symbol, fetched_at)) AS unique_keys
        FROM {BRONZE_TABLE}
        WHERE base_coin = 'BTC'
    """).collect()[0]

    # Compute the latest poll and its contract count in one query, entirely
    # in SQL. Round-tripping the timestamp through Python string formatting
    # (e.g. "'{latest_fetched_at}'") is unreliable, since a timezone-aware
    # Python datetime prints with a +00:00 suffix that may not match the
    # stored value and can silently return zero rows instead of failing loudly.
    latest_poll_row = spark.sql(f"""
        SELECT
            MAX(fetched_at) AS latest_fetched_at,
            COUNT(*) AS latest_poll_contract_count
        FROM {BRONZE_TABLE}
        WHERE base_coin = 'BTC'
          AND fetched_at = (
              SELECT MAX(fetched_at) FROM {BRONZE_TABLE} WHERE base_coin = 'BTC'
          )
    """).collect()[0]
    latest_fetched_at = _to_datetime(latest_poll_row["latest_fetched_at"])

    drift_row = spark.sql(f"""
        SELECT
            SUM(CASE WHEN schema_extra_fields IS NOT NULL
                     AND schema_extra_fields != '[]' THEN 1 ELSE 0 END) AS extra_field_rows,
            SUM(CASE WHEN schema_missing_fields IS NOT NULL
                     AND schema_missing_fields != '[]' THEN 1 ELSE 0 END) AS missing_field_rows
        FROM {BRONZE_TABLE}
        WHERE base_coin = 'BTC'
    """).collect()[0]

    result = {
        "rows": dup_row["rows"],
        "unique_keys": dup_row["unique_keys"],
        "latest_fetched_at": str(latest_fetched_at) if latest_fetched_at else None,
        "latest_poll_contract_count": latest_poll_row["latest_poll_contract_count"],
        "extra_field_rows": drift_row["extra_field_rows"],
        "missing_field_rows": drift_row["missing_field_rows"],
    }

    if result["rows"] != result["unique_keys"]:
        raise ValueError(
            f"Duplicate keys detected in {BRONZE_TABLE}: "
            f"{result['rows']} rows vs {result['unique_keys']} unique keys"
        )

    if latest_fetched_at is None:
        raise ValueError(f"{BRONZE_TABLE} has no rows for base_coin = 'BTC'")

    age_minutes = (
        datetime.now(timezone.utc) - latest_fetched_at
    ).total_seconds() / 60
    result["age_minutes"] = round(age_minutes, 1)

    if age_minutes > MAX_FRESHNESS_MINUTES:
        raise ValueError(
            f"{BRONZE_TABLE} is stale: latest poll is {age_minutes:.1f} min old "
            f"(threshold {MAX_FRESHNESS_MINUTES} min). Ingestion may have stopped."
        )

    if result["latest_poll_contract_count"] < MIN_EXPECTED_CONTRACTS_PER_POLL:
        raise ValueError(
            f"Latest poll at {latest_fetched_at} only has "
            f"{result['latest_poll_contract_count']} contracts "
            f"(expected >= {MIN_EXPECTED_CONTRACTS_PER_POLL}). Possible partial fetch."
        )

    return result


if __name__ == "__main__":
    print(check_bronze_funding_rates(spark))
