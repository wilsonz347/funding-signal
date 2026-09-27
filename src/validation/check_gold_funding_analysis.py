"""
Gold-layer sanity check: funding_rate_analysis.

Confirms:
    - row count and key uniqueness (MERGE key should never duplicate)
    - gold is not falling behind silver (catches a repeatedly failing
      gold job before it goes unnoticed)
    - how many rows are flagged as large moves / frozen (visibility,
      not a hard failure — these are expected to vary)

Run as a validation task depending on the gold transformation task.
"""

SILVER_TABLE = "funding_regime_project.silver.funding_rates"
GOLD_TABLE = "funding_regime_project.gold.funding_rate_analysis"

MAX_LAG_MINUTES = 30


def check_funding_rate_analysis(spark) -> dict:
    dup_row = spark.sql(f"""
        SELECT
            COUNT(*) AS rows,
            COUNT(DISTINCT CONCAT(exchange, symbol, fetched_at)) AS unique_keys,
            SUM(CASE WHEN is_large_move THEN 1 ELSE 0 END) AS large_moves,
            SUM(CASE WHEN is_frozen THEN 1 ELSE 0 END) AS frozen_rows
        FROM {GOLD_TABLE}
    """).collect()[0]

    lag_row = spark.sql(f"""
        SELECT
            (SELECT MAX(fetched_at) FROM {SILVER_TABLE}) AS silver_latest,
            (SELECT MAX(fetched_at) FROM {GOLD_TABLE}) AS gold_latest
    """).collect()[0]

    result = {
        "rows": dup_row["rows"],
        "unique_keys": dup_row["unique_keys"],
        "large_moves": dup_row["large_moves"],
        "frozen_rows": dup_row["frozen_rows"],
        "silver_latest": str(lag_row["silver_latest"]) if lag_row["silver_latest"] else None,
        "gold_latest": str(lag_row["gold_latest"]) if lag_row["gold_latest"] else None,
    }

    if result["rows"] != result["unique_keys"]:
        raise ValueError(
            f"Duplicate keys detected in {GOLD_TABLE}: "
            f"{result['rows']} rows vs {result['unique_keys']} unique keys"
        )

    if lag_row["silver_latest"] is None or lag_row["gold_latest"] is None:
        raise ValueError("Silver or Gold has no data — cannot compute lag")

    lag_minutes = (lag_row["silver_latest"] - lag_row["gold_latest"]).total_seconds() / 60
    result["lag_minutes"] = round(lag_minutes, 1)

    if lag_minutes > MAX_LAG_MINUTES:
        raise ValueError(
            f"Gold is falling behind Silver by {lag_minutes:.1f} min "
            f"(threshold {MAX_LAG_MINUTES} min). Gold job may be failing repeatedly."
        )

    return result


if __name__ == "__main__":
    print(check_funding_rate_analysis(spark))
