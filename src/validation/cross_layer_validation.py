"""
Cross-layer row reconciliation: bronze -> silver -> gold.

Confirms that no rows are silently lost or duplicated as data moves
through the pipeline. Since silver filters bronze to base_coin = 'BTC'
and gold is the same grain as silver (one row per silver row, no
further filtering), all three counts should match once each layer has
finished writing:

    bronze (WHERE base_coin = 'BTC') == silver == gold

A mismatch points to a real problem:
    - bronze count > silver count: rows are being dropped during
      casting/filtering that shouldn't be (or silver simply hasn't
      caught up yet — check lag first).
    - silver count > gold count: rows are being dropped in the gold
      feature step, or gold hasn't caught up yet.
    - any count higher than expected: a MERGE key issue causing
      duplicate inserts (should be caught by the per-layer duplicate
      checks too, but a mismatch here is a second signal).

Run this after gold, once all three layers have had a chance to
process the same batch.
"""

CATALOG = "funding_regime_project"

BRONZE_TABLE = f"{CATALOG}.bronze.raw_funding_rates"
SILVER_TABLE = f"{CATALOG}.silver.funding_rates"
GOLD_TABLE = f"{CATALOG}.gold.funding_rate_analysis"


def check_row_reconciliation(spark) -> dict:
    bronze_count = spark.sql(f"""
        SELECT COUNT(*) AS n FROM {BRONZE_TABLE} WHERE base_coin = 'BTC'
    """).collect()[0]["n"]

    silver_count = spark.sql(f"""
        SELECT COUNT(*) AS n FROM {SILVER_TABLE}
    """).collect()[0]["n"]

    gold_count = spark.sql(f"""
        SELECT COUNT(*) AS n FROM {GOLD_TABLE}
    """).collect()[0]["n"]

    result = {
        "bronze_count": bronze_count,
        "silver_count": silver_count,
        "gold_count": gold_count,
        "bronze_minus_silver": bronze_count - silver_count,
        "silver_minus_gold": silver_count - gold_count,
    }

    if bronze_count != silver_count:
        raise ValueError(
            f"Row count mismatch bronze -> silver: bronze has {bronze_count} "
            f"BTC rows, silver has {silver_count}. Difference of "
            f"{result['bronze_minus_silver']} rows — check silver's lag "
            f"first, then investigate dropped/duplicated rows."
        )

    if silver_count != gold_count:
        raise ValueError(
            f"Row count mismatch silver -> gold: silver has {silver_count} "
            f"rows, gold has {gold_count}. Difference of "
            f"{result['silver_minus_gold']} rows — check gold's lag "
            f"first, then investigate dropped/duplicated rows."
        )

    return result


if __name__ == "__main__":
    print(check_row_reconciliation(spark))
