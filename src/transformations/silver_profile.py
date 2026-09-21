"""
Profiles bronze rows against a hypothesis of expected type/nullability
per field to decide cleaning rules.
"""

from datetime import datetime

FIELD_SPECS = {
    "exchange": {"type": "str", "nullable": False},
    "symbol": {"type": "str", "nullable": False},
    "base_coin": {"type": "str", "nullable": False},
    "rate": {"type": "float", "nullable": False},
    "predicted_rate": {"type": "float", "nullable": True},
    "interval_hours": {"type": "int", "nullable": False},
    "next_funding_time": {"type": "datetime", "nullable": False},
    "updated_at": {"type": "datetime", "nullable": False},
    "margin_type": {"type": "str", "nullable": False},
    "asset_class": {"type": "str", "nullable": False},
    "mark_price": {"type": "float", "nullable": False},
    "mark_price_updated_at": {"type": "datetime", "nullable": False},
    "open_interest": {"type": "float", "nullable": True},
    "market_cap_rank": {"type": "int", "nullable": True},
    "age_seconds": {"type": "int", "nullable": False},
    "data_source": {"type": "str", "nullable": False},
    "freshness_sla_seconds": {"type": "int", "nullable": False},
    "is_stale": {"type": "bool", "nullable": False},
}


def _can_cast(value, expected_type: str) -> bool:
    if value is None:
        return True
    try:
        if expected_type == "float":
            float(value)
        elif expected_type == "int":
            int(value)
        elif expected_type == "bool":
            if not isinstance(value, bool):
                return False
        elif expected_type == "datetime":
            datetime.fromisoformat(value)
        elif expected_type == "str":
            if not isinstance(value, str):
                return False
        return True
    except (ValueError, TypeError):
        return False


def profile_fields(rows: list[dict]) -> dict:
    """
    Returns, per field: null_count, unexpected_null_count, 
    cast_failure_count, and up to 3 example
    values that failed to cast, for manual inspection.
    """
    report = {}

    for field, spec in FIELD_SPECS.items():
        null_count = 0
        unexpected_null_count = 0
        cast_failure_count = 0
        failure_examples = []

        for row in rows:
            value = row.get(field)

            if value is None:
                null_count += 1
                if not spec["nullable"]:
                    unexpected_null_count += 1
                continue

            if not _can_cast(value, spec["type"]):
                cast_failure_count += 1
                if len(failure_examples) < 3:
                    failure_examples.append(value)

        report[field] = {
            "null_count": null_count,
            "unexpected_null_count": unexpected_null_count,
            "cast_failure_count": cast_failure_count,
            "cast_failure_examples": failure_examples,
        }

    return report
