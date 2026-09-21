from src.transformations.silver_transform import clean_rows
import pandas as pd
from delta.tables import DeltaTable

CATALOG = "funding_regime_project"
BRONZE_TABLE = f"{CATALOG}.bronze.raw_funding_rates"
SILVER_TABLE = f"{CATALOG}.silver.funding_rates"

# Watermark for incremental read: max fetched_at already in silver
try:
    spark.sql(f"DESCRIBE TABLE {SILVER_TABLE}")
    table_exists = True
except Exception:
    table_exists = False
    
watermark = None
if table_exists:
    watermark = spark.sql(f"SELECT MAX(fetched_at) AS wm FROM {SILVER_TABLE}").collect()[0]["wm"]

where_clause = "exchange = 'Binance' AND symbol = 'BTCUSDT'"
if watermark:
    where_clause += f" AND fetched_at > '{watermark}'"

bronze_rows = [r.asDict() for r in spark.sql(f"SELECT * FROM {BRONZE_TABLE} WHERE {where_clause}").collect()]

if not bronze_rows:
    dbutils.notebook.exit("no new rows since last run")

# Clean and create a DataFrame
cleaned = clean_rows(bronze_rows)
sdf = spark.createDataFrame(pd.DataFrame(cleaned))

if not table_exists:
    # Append the table
    sdf.write.format("delta").mode("append").saveAsTable(SILVER_TABLE)
    print(f"Created {SILVER_TABLE}, {sdf.count()} rows")
else:
    # Incremental load
    # Insert if key (exchange, symbol, fetched_at) does not exist
    target = DeltaTable.forName(spark, SILVER_TABLE)
    (target.alias("s")
        .merge(sdf.alias("n"), "s.exchange = n.exchange AND s.symbol = n.symbol AND s.fetched_at = n.fetched_at")
        .whenNotMatchedInsertAll()
        .execute())
    print(f"Merged {sdf.count()} rows into {SILVER_TABLE}")
