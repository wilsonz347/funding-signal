"""
Cast Bronze values → typed values
Run find_quality_issues() on the typed values
Calculate poll_lag_seconds
Return the cleaned Silver row
"""

import json
from datetime import datetime

from src.transformations.silver_profile import FIELD_SPECS
from src.transformations.quality_checks import find_quality_issues
from src.transformations.silver_normalize import normalize_rate, annualize_rate


def _cast_value(value, expected_type: str):
    """Returns (casted_value, failed). Never raises."""
    if value is None:
        return None, False

    try:
        if expected_type == "float":
            return float(value), False
        elif expected_type == "int":
            return int(value), False
        elif expected_type == "bool":
            if isinstance(value, bool):
                return value, False
            return None, True
        elif expected_type == "datetime":
            return datetime.fromisoformat(value), False
        elif expected_type == "str":
            if isinstance(value, str):
                return value, False
            return None, True
    except (ValueError, TypeError):
        return None, True

    return None, True  # unknown expected_type


def compute_poll_lag_seconds(fetched_at, updated_at):
    if fetched_at is None or updated_at is None:
        return None

    return (fetched_at - updated_at).total_seconds()


def clean_row(bronze_row: dict) -> dict:
    """
    Casts one bronze row to silver types.
    Returns a dict with the same keys as bronze_row, plus a new
    "silver_cast_issues" field with a list of fields that failed to
    cast.
    """
    cleaned = {}
    cast_issues = []

    for field, spec in FIELD_SPECS.items():
        raw_value = bronze_row.get(field)
        casted, failed = _cast_value(raw_value, spec["type"])
        cleaned[field] = casted
        if failed:
            cast_issues.append(field)

    cleaned["silver_cast_issues"] = json.dumps(cast_issues)

    cleaned["bronze_schema_extra_fields"] = bronze_row.get("schema_extra_fields")
    cleaned["bronze_schema_missing_fields"] = bronze_row.get("schema_missing_fields")

    cleaned["rate_per_8h"] = normalize_rate(cleaned.get("rate"), cleaned.get("interval_hours"))
    cleaned["rate_annualized"] = annualize_rate(cleaned.get("rate"), cleaned.get("interval_hours"))
    cleaned["poll_lag_seconds"] = compute_poll_lag_seconds(cleaned.get("fetched_at"), cleaned.get("updated_at"))

    cleaned["silver_quality_issues"] = json.dumps(
        find_quality_issues(
            rate=cleaned.get("rate"),
            interval_hours=cleaned.get("interval_hours"),
            mark_price=cleaned.get("mark_price"),
            open_interest=cleaned.get("open_interest"),
            fetched_at=cleaned.get("fetched_at"),
            updated_at=cleaned.get("updated_at"),
            next_funding_time=cleaned.get("next_funding_time"),
            age_seconds=cleaned.get("age_seconds"),
        )
    )

    return cleaned


def clean_rows(bronze_rows: list[dict]) -> list[dict]:
    return [clean_row(row) for row in bronze_rows]
