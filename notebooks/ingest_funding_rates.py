from src.ingestion.sharpe_wrapper import fetch_current_funding_rates_safe
from src.ingestion.bronze_transform import explode_funding_response, BronzeTransformError
import pandas as pd

CATALOG = "funding_regime_project"
TABLE = f"{CATALOG}.bronze.raw_funding_rates"

api_key = dbutils.secrets.get(catalog=CATALOG, schema="bronze", key="sharpe_api_key")
outcome = fetch_current_funding_rates_safe(api_key)

if not outcome["success"]:
    # Skip this cycle. No write happens, nothing corrupts the table.
    print(f"Ingestion cycle skipped: {outcome['reason']}")
    dbutils.notebook.exit(f"skipped: {outcome['reason']}")

result = outcome["result"]

try:
    rows = explode_funding_response(
        payload_str=result["payload"],
        fetched_at=result["fetched_at"],
        status_code=result["status_code"],
    )
except BronzeTransformError as e:
    print(f"Ingestion cycle skipped: transform error: {e}")
    dbutils.notebook.exit(f"skipped: transform_error: {e}")

pdf = pd.DataFrame(rows)
sdf = spark.createDataFrame(pdf)

sdf.write.format("delta").mode("append").saveAsTable(TABLE)

print(f"Wrote {len(rows)} rows to {TABLE}")
