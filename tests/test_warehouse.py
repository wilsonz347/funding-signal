# tests/test_warehouse.py
"""
Tests for src/agent/warehouse.py.
"""

from src.agent.warehouse import (
    apply_cap,
    parse_describe,
    ColumnInfo,
)


def test_apply_cap_empty():
    assert apply_cap([], 50) == ([], False)


def test_apply_cap_exact_limit():
    rows = list(range(50))
    assert apply_cap(rows, 50) == (rows, False)


def test_apply_cap_over_limit():
    rows = list(range(51))
    capped, truncated = apply_cap(rows, 50)

    assert capped == list(range(50))
    assert truncated is True


def test_parse_describe_stops_at_partition_section():
    raw_rows = [
        {
            "col_name": "exchange",
            "data_type": "string",
            "comment": "Exchange name",
        },
        {
            "col_name": "fetched_at",
            "data_type": "timestamp",
            "comment": None,
        },
        {
            "col_name": "# Partition Information",
            "data_type": None,
            "comment": None,
        },
        {
            "col_name": "extra_metadata",
            "data_type": "string",
            "comment": None,
        },
    ]

    result = parse_describe(raw_rows)

    assert result == [
        ColumnInfo("exchange", "string", "Exchange name"),
        ColumnInfo("fetched_at", "timestamp", None),
    ]
