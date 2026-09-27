from src.transformations.gold_funding_analysis import (
    calculate_funding_change,
    calculate_oi_change,
    calculate_price_change,
    is_frozen,
    is_large_move,
    LARGE_MOVE_THRESHOLD,
)

import pandas as pd
from delta.tables import DeltaTable
from pyspark.sql import functions as F
from pyspark.sql.window import Window


CATALOG = "funding_regime_project"

SILVER_TABLE = f"{CATALOG}.silver.funding_rates"
GOLD_TABLE = f"{CATALOG}.gold.funding_rate_analysis"

# Number of previous observations needed to determine
# whether a funding rate has remained frozen.
FROZEN_LOOKBACK = 5


# Check whether Gold table exists
try:
    spark.sql(f"DESCRIBE TABLE {GOLD_TABLE}")
    gold_exists = True
except Exception:
    gold_exists = False


# Get Gold watermark directly from the Gold table itself.
watermark = None

if gold_exists:
    watermark = (
        spark.sql(f"SELECT MAX(fetched_at) AS wm FROM {GOLD_TABLE}")
        .collect()[0]["wm"]
    )


# Read only new Silver rows
where_clause = "base_coin = 'BTC'"

if watermark:
    where_clause += f" AND fetched_at > '{watermark}'"

new_rows = spark.sql(f"SELECT * FROM {SILVER_TABLE} WHERE {where_clause}")

if new_rows.isEmpty():
    dbutils.notebook.exit("no new rows since last run")


# Find earliest new observation
earliest_new = new_rows.select(F.min("fetched_at")).collect()[0][0]


# Read historical lookback rows.
#
# Need enough previous observations per contract to calculate:
# - previous funding rate (up to 5, for frozen detection)
# - previous OI
# - previous price
#
# Bounded to a 2-day window so this doesn't scan the whole table.
historical_rows = spark.sql(f"""
    SELECT *
    FROM {SILVER_TABLE}
    WHERE base_coin = 'BTC'
      AND fetched_at >= '{earliest_new}' - INTERVAL 2 DAYS
      AND fetched_at < '{earliest_new}'
""")

historical_window = (
    Window
    .partitionBy("exchange", "symbol")
    .orderBy(F.col("fetched_at").desc())
)

historical_rows = (
    historical_rows
    .withColumn("row_num", F.row_number().over(historical_window))
    .filter(F.col("row_num") <= FROZEN_LOOKBACK)
    .drop("row_num")
)


# Combine lookback rows with new rows
input_df = historical_rows.unionByName(new_rows)


# Calculate previous observations per contract.
#
# This lag computation stays in Spark (cheap, no Python function
# involved) — only the feature calculations below run on the driver.
calculation_window = (
    Window
    .partitionBy("exchange", "symbol")
    .orderBy("fetched_at")
)

input_df = (
    input_df
    .withColumn("previous_rate", F.lag("rate_per_8h", 1).over(calculation_window))
    .withColumn("previous_rate_2", F.lag("rate_per_8h", 2).over(calculation_window))
    .withColumn("previous_rate_3", F.lag("rate_per_8h", 3).over(calculation_window))
    .withColumn("previous_rate_4", F.lag("rate_per_8h", 4).over(calculation_window))
    .withColumn("previous_rate_5", F.lag("rate_per_8h", 5).over(calculation_window))
    .withColumn("previous_oi", F.lag("open_interest", 1).over(calculation_window))
    .withColumn("previous_price", F.lag("mark_price", 1).over(calculation_window))
)


# Calculate Gold features on the driver.
#
# Matches Silver's clean_row pattern: collect to the driver, run the
# plain Python functions from src/, rebuild the Spark DataFrame.
rows = [row.asDict() for row in input_df.collect()]

for row in rows:
    row["funding_change"] = calculate_funding_change(
        row.get("rate_per_8h"), row.get("previous_rate")
    )
    row["oi_change"] = calculate_oi_change(
        row.get("open_interest"), row.get("previous_oi")
    )
    row["price_change"] = calculate_price_change(
        row.get("mark_price"), row.get("previous_price")
    )
    row["is_large_move"] = is_large_move(row["funding_change"], LARGE_MOVE_THRESHOLD)
    row["is_frozen"] = is_frozen(
        row.get("rate_per_8h"),
        [
            row.get("previous_rate"),
            row.get("previous_rate_2"),
            row.get("previous_rate_3"),
            row.get("previous_rate_4"),
            row.get("previous_rate_5"),
        ],
    )

gold_df = spark.createDataFrame(pd.DataFrame(rows))


# Select Gold columns
gold_df = gold_df.select(
    "exchange",
    "symbol",
    "margin_type",
    "fetched_at",
    "rate_per_8h",
    "funding_change",
    "is_large_move",
    "is_frozen",
    "open_interest",
    "oi_change",
    "mark_price",
    "price_change",
)


# Keep only new rows
if watermark:
    gold_df = gold_df.filter(F.col("fetched_at") > F.lit(watermark))


# Write Gold
if not gold_exists:
    (
        gold_df.write
        .format("delta")
        .mode("append")
        .saveAsTable(GOLD_TABLE)
    )
else:
    target = DeltaTable.forName(spark, GOLD_TABLE)
    (
        target.alias("g")
        .merge(
            gold_df.alias("n"),
            """
            g.exchange = n.exchange
            AND g.symbol = n.symbol
            AND g.fetched_at = n.fetched_at
            """,
        )
        .whenMatchedUpdateAll()
        .whenNotMatchedInsertAll()
        .execute()
    )
