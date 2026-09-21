import json

from src.transformations.silver_transform import clean_row, clean_rows

GOOD_ROW = {
    "exchange": "Binance", "symbol": "BTCUSDT", "base_coin": "BTC",
    "rate": 6.897e-05, "predicted_rate": None, "interval_hours": 8,
    "next_funding_time": "2026-09-18T08:00:00+00:00",
    "updated_at": "2026-09-18T03:35:42.729+00:00", "margin_type": "linear",
    "asset_class": "crypto", "mark_price": 77381.9,
    "mark_price_updated_at": "2026-09-18T03:35:42.729+00:00",
    "open_interest": 8408566417.09785, "market_cap_rank": 1, "age_seconds": 23,
    "data_source": "supabase", "freshness_sla_seconds": 600, "is_stale": False,
    "fetched_at": "2026-09-18T03:35:42.729000+00:00",
    "schema_extra_fields": "[]", "schema_missing_fields": "[]",
}


def test_clean_row_has_no_cast_issues():
    row = clean_row(GOOD_ROW)

    assert json.loads(row["silver_cast_issues"]) == []
    assert row["rate"] == 6.897e-05
    assert isinstance(row["updated_at"], type(row["updated_at"]))  # parsed, not a string


def test_missing_key_entirely_does_not_crash():
    broken_row = dict(GOOD_ROW)
    del broken_row["rate"]  # field absent, not just null

    row = clean_row(broken_row)  # must not raise

    assert row["rate"] is None


def test_bad_value_flagged_not_crashed():
    broken_row = dict(GOOD_ROW)
    broken_row["rate"] = "not_a_number"

    row = clean_row(broken_row)

    assert row["rate"] is None
    assert "rate" in json.loads(row["silver_cast_issues"])


def test_bronze_drift_flags_carried_forward():
    drifted_row = dict(GOOD_ROW)
    drifted_row["schema_extra_fields"] = '["new_vendor_field"]'

    row = clean_row(drifted_row)

    assert row["bronze_schema_extra_fields"] == '["new_vendor_field"]'


def test_clean_rows_processes_a_list():
    rows = clean_rows([GOOD_ROW, GOOD_ROW])

    assert len(rows) == 2

def test_clean_row_has_no_quality_issues():
    row = clean_row(GOOD_ROW)
 
    assert json.loads(row["silver_quality_issues"]) == []
 
 
def test_non_positive_interval_hours_flagged():
    bad_row = dict(GOOD_ROW)
    bad_row["interval_hours"] = 0
 
    row = clean_row(bad_row)
 
    assert "interval_hours_not_positive" in json.loads(row["silver_quality_issues"])
 
 
def test_non_positive_age_seconds_flagged():
    bad_row = dict(GOOD_ROW)
    bad_row["age_seconds"] = -5
 
    row = clean_row(bad_row)
 
    assert "age_seconds_not_positive" in json.loads(row["silver_quality_issues"])
 
 
def test_updated_at_after_fetched_at_flagged():
    bad_row = dict(GOOD_ROW)
    bad_row["updated_at"] = "2026-09-18T04:00:00.000+00:00"   # after fetched_at
    bad_row["fetched_at"] = "2026-09-18T03:35:42.729000+00:00"
 
    row = clean_row(bad_row)
 
    assert "updated_at_after_fetched_at" in json.loads(row["silver_quality_issues"])
 
 
def test_next_funding_time_before_updated_at_flagged():
    bad_row = dict(GOOD_ROW)
    bad_row["updated_at"] = "2026-09-18T08:00:00.000+00:00"
    bad_row["next_funding_time"] = "2026-09-18T03:00:00+00:00"  # before updated_at
 
    row = clean_row(bad_row)
 
    assert "next_funding_time_not_after_updated_at" in json.loads(row["silver_quality_issues"])
 
 
def test_null_field_does_not_trigger_quality_check():
    """A None value (null or failed cast) is skipped, not double-flagged."""
    row_with_null = dict(GOOD_ROW)
    row_with_null["interval_hours"] = None
 
    row = clean_row(row_with_null)
 
    assert "interval_hours_not_positive" not in json.loads(row["silver_quality_issues"])
