from src.transformations.silver_profile import profile_fields

GOOD_ROW = {
    "exchange": "Binance", "symbol": "BTCUSDT", "base_coin": "BTC",
    "rate": 6.897e-05, "predicted_rate": None, "interval_hours": 8,
    "next_funding_time": "2026-09-18T08:00:00+00:00",
    "updated_at": "2026-09-18T03:35:42.729+00:00", "margin_type": "linear",
    "asset_class": "crypto", "mark_price": 77381.9,
    "mark_price_updated_at": "2026-09-18T03:35:42.729+00:00",
    "open_interest": 8408566417.09785, "market_cap_rank": 1, "age_seconds": 23,
    "data_source": "supabase", "freshness_sla_seconds": 600, "is_stale": False,
}


def test_clean_row_has_no_issues():
    report = profile_fields([GOOD_ROW])

    assert report["rate"]["unexpected_null_count"] == 0
    assert report["rate"]["cast_failure_count"] == 0
    assert report["predicted_rate"]["null_count"] == 1
    assert report["predicted_rate"]["unexpected_null_count"] == 0  # nullable, expected


def test_unexpected_null_on_required_field():
    bad_row = dict(GOOD_ROW)
    bad_row["rate"] = None

    report = profile_fields([bad_row])

    assert report["rate"]["unexpected_null_count"] == 1


def test_cast_failure_on_malformed_number():
    bad_row = dict(GOOD_ROW)
    bad_row["rate"] = "not_a_number"

    report = profile_fields([bad_row])

    assert report["rate"]["cast_failure_count"] == 1
    assert "not_a_number" in report["rate"]["cast_failure_examples"]


def test_cast_failure_on_malformed_timestamp():
    bad_row = dict(GOOD_ROW)
    bad_row["updated_at"] = "not-a-timestamp"

    report = profile_fields([bad_row])

    assert report["updated_at"]["cast_failure_count"] == 1


def test_expected_null_on_nullable_field_not_flagged():
    row = dict(GOOD_ROW)
    row["open_interest"] = None

    report = profile_fields([row])

    assert report["open_interest"]["null_count"] == 1
    assert report["open_interest"]["unexpected_null_count"] == 0
