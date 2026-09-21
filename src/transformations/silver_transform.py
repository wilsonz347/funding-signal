"""
Casts bronze rows into properly-typed silver rows.
"""

import json
from datetime import datetime

from src.transformations.silver_profile import FIELD_SPECS


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


def check_quality(row: dict) -> list[str]:
    """
    Sanity/cross-field checks, run on already-cast values.
    """
    issues = []
 
    interval_hours = row.get("interval_hours")
    if interval_hours is not None and interval_hours <= 0:
        issues.append("interval_hours_not_positive")
 
    age_seconds = row.get("age_seconds")
    if age_seconds is not None and age_seconds <= 0:
        issues.append("age_seconds_not_positive")
 
    updated_at = row.get("updated_at")
    next_funding_time = row.get("next_funding_time")
    fetched_at_raw = row.get("fetched_at")
 
    fetched_at = None
    if fetched_at_raw is not None:
        try:
            fetched_at = datetime.fromisoformat(fetched_at_raw)
        except (ValueError, TypeError):
            pass
 
    if updated_at is not None and fetched_at is not None and updated_at > fetched_at:
        issues.append("updated_at_after_fetched_at")
 
    if updated_at is not None and next_funding_time is not None and next_funding_time <= updated_at:
        issues.append("next_funding_time_not_after_updated_at")
 
    return issues


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

    cleaned["fetched_at"] = bronze_row.get("fetched_at")
    cleaned["silver_cast_issues"] = json.dumps(cast_issues)
    cleaned["silver_quality_issues"] = json.dumps(check_quality(cleaned))

    cleaned["bronze_schema_extra_fields"] = bronze_row.get("schema_extra_fields")
    cleaned["bronze_schema_missing_fields"] = bronze_row.get("schema_missing_fields")

    return cleaned


def clean_rows(bronze_rows: list[dict]) -> list[dict]:
    return [clean_row(row) for row in bronze_rows]
