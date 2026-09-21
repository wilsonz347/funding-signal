from src.transformations.silver_profile import profile_fields

CATALOG = "funding_regime_project"
BRONZE_TABLE = f"{CATALOG}.bronze.raw_funding_rates"

df = spark.sql(f"""
    SELECT *
    FROM {BRONZE_TABLE}
    WHERE exchange = 'Binance' AND symbol = 'BTCUSDT'
""")

rows = [r.asDict() for r in df.collect()]
report = profile_fields(rows)

for field, stats in report.items():
    if stats["unexpected_null_count"] > 0 or stats["cast_failure_count"] > 0:
        print(f"⚠ {field}: {stats}")

report