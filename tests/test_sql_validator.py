# tests/test_sql_validator.py
"""Tests for the SQL validator."""

import re

import pytest

from src.agent.catalog import Catalog
from src.agent.sql_validator import SQLValidator

T = "funding_regime_project.gold.funding_rate_analysis"
COLUMNS = ["exchange", "symbol", "fetched_at", "rate_per_8h", "funding_change", "open_interest", "oi_change"]
MAX_ROWS = 100

# Create a validator 
validator = SQLValidator(
    Catalog({
        "tables": [{"name": T, "columns": {c: {} for c in COLUMNS}}],
        "policies": {"max_query_rows": MAX_ROWS},
    })
)

# Helper
def validated_sql(sql: str) -> str:
    result = validator.validate(sql)
    assert result.ok, result.errors
    assert result.sql is not None
    return result.sql

# Test cases
@pytest.mark.parametrize("sql", [
    f"SELECT exchange, COUNT(*) FROM {T} GROUP BY exchange",
    f"SELECT COUNT(DISTINCT symbol) FROM {T}",
    f"SELECT exchange FROM {T.upper()}",
    f"SELECT t.exchange FROM {T} t",
    f"SELECT exchange FROM {T} WHERE fetched_at >= current_timestamp() - INTERVAL 1 DAY",
    f"SELECT exchange FROM {T} WHERE symbol IN (SELECT symbol FROM {T})",
    # aliases: outer query, CTE, subquery, window function
    f"SELECT exchange, AVG(rate_per_8h) AS avg_rate FROM {T} GROUP BY exchange ORDER BY avg_rate DESC",
    f"SELECT symbol, MAX(funding_change) AS m FROM {T} GROUP BY symbol HAVING m > 0.001",
    f"WITH x AS (SELECT exchange, COUNT(*) AS n FROM {T} GROUP BY exchange) SELECT exchange, n FROM x ORDER BY n DESC",
    f"SELECT exchange, n FROM (SELECT exchange, COUNT(*) AS n FROM {T} GROUP BY exchange) s ORDER BY n",
    f"WITH r AS (SELECT symbol, rate_per_8h, ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY fetched_at DESC) AS rn "
    f"FROM {T}) SELECT symbol, rate_per_8h FROM r WHERE rn = 1",
])
def test_accepts(sql):
    result = validator.validate(sql)
    assert result.ok, result.errors


@pytest.mark.parametrize("sql", [
    # input / syntax
    "", "   ", ";", "SELEC garbage (",
    # not a plain SELECT
    f"DROP TABLE {T}", f"DELETE FROM {T}", f"INSERT INTO {T} VALUES (1)", f"UPDATE {T} SET exchange = 'x'",
    f"SELECT exchange INTO new_table FROM {T}",
    # multiple statements
    f"SELECT exchange FROM {T}; DROP TABLE {T}",
    # tables
    "SELECT exchange FROM other_catalog.gold.funding_rate_analysis",
    "SELECT exchange FROM funding_rate_analysis",
    "SELECT exchange FROM gold.funding_rate_analysis",
    f"SELECT exchange FROM {T} WHERE symbol IN (SELECT symbol FROM x.y.z)",
    "SELECT exchange FROM read_files('s3://bucket/path')",
    "SELECT 1",
    # columns
    f"SELECT secret FROM {T}",
    f"SELECT exchange FROM {T} WHERE bogus > 1",
    f"SELECT exchange FROM {T} ORDER BY nonexistent",
])
def test_rejects(sql):
    result = validator.validate(sql)
    assert not result.ok and result.errors and result.sql is None


def test_unknown_column_error_lists_available_columns():
    errors = validator.validate(f"SELECT secret FROM {T}").errors
    assert "secret" in errors[0] and "exchange" in errors[0]

def trailing_limit(sql: str) -> str:
    match = re.search(r"LIMIT (\d+)$", sql)
    assert match is not None, f"No trailing LIMIT found in SQL: {sql}"
    return match.group(1)

def test_smaller_limit_is_kept():
    assert trailing_limit(validated_sql(
        f"SELECT exchange FROM {T} LIMIT 10"
    )) == "10"

def test_limit_added_when_missing():
    assert trailing_limit(validated_sql(
        f"SELECT exchange FROM {T}"
    )) == str(MAX_ROWS)

def test_oversized_limit_is_capped():
    assert trailing_limit(validated_sql(
        f"SELECT exchange FROM {T} LIMIT 1000000"
    )) == str(MAX_ROWS)


def test_non_literal_limit_is_replaced_by_cap():
    assert trailing_limit(validated_sql(
        f"SELECT exchange FROM {T} LIMIT 10 + 5"
    )) == str(MAX_ROWS)


def test_arithmetic_limit_cannot_bypass_cap():
    assert trailing_limit(validated_sql(
        f"SELECT exchange FROM {T} LIMIT 1 + 1000000"
    )) == str(MAX_ROWS)
