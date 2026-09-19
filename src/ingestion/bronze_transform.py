"""
Transforms a raw Sharpe 'current' funding-rate response into bronze rows.

One response contains many exchange/symbol records in a single JSON array.
This module explodes that array into one row per record, keeping every
vendor field as-is (no renaming, no type coercion beyond table columns),
and attaches:
  - poll-level metadata (shared across all rows from the same poll)
  - the individual record's own raw JSON (not the whole response)
  - a visible flag for any field the vendor added or removed since we
    last looked to monitor change in schema
"""

import json

# Expected schema
EXPECTED_FIELDS = {
    "exchange",
    "symbol",
    "base_coin",
    "rate",
    "predicted_rate",
    "interval_hours",
    "next_funding_time",
    "updated_at",
    "margin_type",
    "asset_class",
    "mark_price",
    "mark_price_updated_at",
    "open_interest",
    "market_cap_rank",
    "age_seconds",
    "data_source",
    "freshness_sla_seconds",
    "is_stale",
}


class BronzeTransformError(Exception):
    """Raised when the response payload isn't valid JSON or lacks a
    top-level 'data' array."""
    pass


def explode_funding_response(payload_str: str, fetched_at: str, status_code: int) -> list[dict]:
    """
    Turns one raw 'current' response into a list of bronze-ready rows.

    Args:
        payload_str: the raw response body, as returned by
            sharpe_client.fetch_current_funding_rates (result["payload"]).
        fetched_at: ingestion timestamp from the same result.
        status_code: HTTP status from the same result. Callers should only
            pass 200 responses here.

    Returns:
        One dict per exchange/symbol record, each containing poll metadata,
        every expected vendor field (None if absent), the record's own raw
        JSON, and drift flags.
    """
    try:
        parsed = json.loads(payload_str)
    except json.JSONDecodeError as e:
        raise BronzeTransformError(f"Payload is not valid JSON: {e}") from e

    if "data" not in parsed or not isinstance(parsed["data"], list):
        raise BronzeTransformError("Payload has no top-level 'data' array")

    rows = []
    for record in parsed["data"]:
        record_keys = set(record.keys())
        extra_fields = sorted(record_keys - EXPECTED_FIELDS)
        missing_fields = sorted(EXPECTED_FIELDS - record_keys)

        row = {
            "fetched_at": fetched_at,
            "status_code": status_code,
            "raw_record_json": json.dumps(record),
            "schema_extra_fields": json.dumps(extra_fields),
            "schema_missing_fields": json.dumps(missing_fields),
        }
        for field in EXPECTED_FIELDS:
            row[field] = record.get(field)

        rows.append(row)

    return rows
