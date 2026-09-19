"""
Tests for src/ingestion/bronze_transform.py.

Uses the real Binance BTC payload (frozen as a fixture),
plus synthetic payloads to detect schema-drift.
"""

import json
import pytest

from src.ingestion.bronze_transform import explode_funding_response, BronzeTransformError

FETCHED_AT = "2026-09-18T03:35:42.729000+00:00"
STATUS_CODE = 200

# Real response sample, frozen from an actual Sharpe 'current' pull.
REAL_BTC_BINANCE_PAYLOAD = json.dumps({
    "data": [
        {
            "exchange": "Binance", "symbol": "BTCUSD_PERP", "base_coin": "BTC",
            "rate": 0.0001, "predicted_rate": None, "interval_hours": 8,
            "next_funding_time": "2026-09-18T08:00:00+00:00",
            "updated_at": "2026-09-18T03:35:42.729+00:00", "margin_type": "inverse",
            "asset_class": "crypto", "mark_price": 77381.9,
            "mark_price_updated_at": "2026-09-18T03:35:42.729+00:00",
            "open_interest": None, "market_cap_rank": 1, "age_seconds": 23,
            "data_source": "supabase", "freshness_sla_seconds": 600, "is_stale": False,
        },
        {
            "exchange": "Binance", "symbol": "BTCUSDT", "base_coin": "BTC",
            "rate": 6.897e-05, "predicted_rate": None, "interval_hours": 8,
            "next_funding_time": "2026-09-18T08:00:00+00:00",
            "updated_at": "2026-09-18T03:35:42.729+00:00", "margin_type": "linear",
            "asset_class": "crypto", "mark_price": 77381.9,
            "mark_price_updated_at": "2026-09-18T03:35:42.729+00:00",
            "open_interest": 8408566417.09785, "market_cap_rank": 1, "age_seconds": 23,
            "data_source": "supabase", "freshness_sla_seconds": 600, "is_stale": False,
        },
    ]
})


def test_explodes_one_row_per_record():
    rows = explode_funding_response(REAL_BTC_BINANCE_PAYLOAD, FETCHED_AT, STATUS_CODE)

    assert len(rows) == 2
    symbols = {row["symbol"] for row in rows}
    assert symbols == {"BTCUSD_PERP", "BTCUSDT"}


def test_poll_metadata_attached_to_every_row():
    rows = explode_funding_response(REAL_BTC_BINANCE_PAYLOAD, FETCHED_AT, STATUS_CODE)

    for row in rows:
        assert row["fetched_at"] == FETCHED_AT
        assert row["status_code"] == STATUS_CODE


def test_raw_record_json_is_per_record_not_whole_response():
    rows = explode_funding_response(REAL_BTC_BINANCE_PAYLOAD, FETCHED_AT, STATUS_CODE)
    btcusdt_row = next(r for r in rows if r["symbol"] == "BTCUSDT")

    stored_record = json.loads(btcusdt_row["raw_record_json"])
    assert stored_record["symbol"] == "BTCUSDT"
    assert "data" not in stored_record


def test_no_drift_flags_on_known_schema():
    rows = explode_funding_response(REAL_BTC_BINANCE_PAYLOAD, FETCHED_AT, STATUS_CODE)

    for row in rows:
        assert json.loads(row["schema_extra_fields"]) == []
        assert json.loads(row["schema_missing_fields"]) == []


def test_flags_unexpected_new_field():
    payload = json.dumps({
        "data": [{
            "exchange": "Binance", "symbol": "BTCUSDT", "base_coin": "BTC",
            "rate": 0.0001, "predicted_rate": None, "interval_hours": 8,
            "next_funding_time": "2026-09-18T08:00:00+00:00",
            "updated_at": "2026-09-18T03:35:42.729+00:00", "margin_type": "linear",
            "asset_class": "crypto", "mark_price": 77381.9,
            "mark_price_updated_at": "2026-09-18T03:35:42.729+00:00",
            "open_interest": 8408566417.0, "market_cap_rank": 1, "age_seconds": 23,
            "data_source": "supabase", "freshness_sla_seconds": 600, "is_stale": False,
            "settlement_currency": "USDT",  # field the vendor didn't have before
        }]
    })

    rows = explode_funding_response(payload, FETCHED_AT, STATUS_CODE)

    assert json.loads(rows[0]["schema_extra_fields"]) == ["settlement_currency"]
    assert json.loads(rows[0]["schema_missing_fields"]) == []


def test_flags_missing_expected_field():
    payload = json.dumps({
        "data": [{
            "exchange": "Binance", "symbol": "BTCUSDT", "base_coin": "BTC",
            "rate": 0.0001,
            # interval_hours intentionally omitted for testing
        }]
    })

    rows = explode_funding_response(payload, FETCHED_AT, STATUS_CODE)

    assert "interval_hours" in json.loads(rows[0]["schema_missing_fields"])
    assert rows[0]["interval_hours"] is None  # doesn't crash, just null


def test_invalid_json_raises_bronze_transform_error():
    with pytest.raises(BronzeTransformError):
        explode_funding_response("not valid json {{{", FETCHED_AT, STATUS_CODE)


def test_missing_data_key_raises_bronze_transform_error():
    with pytest.raises(BronzeTransformError):
        explode_funding_response(json.dumps({"unexpected": []}), FETCHED_AT, STATUS_CODE)
