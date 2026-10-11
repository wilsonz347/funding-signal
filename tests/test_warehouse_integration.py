# tests/test_warehouse_integration.py
"""
Tests for src/agent/warehouse.py.
"""

import pytest

from src.agent.settings import Settings
from src.agent.warehouse import DatabricksWarehouse, PermissionDeniedError


GOLD_TABLE = "funding_regime_project.gold.funding_rate_analysis"

@pytest.fixture
def warehouse():
    with DatabricksWarehouse(Settings.from_env()) as wh:
        yield wh

def test_query_and_metadata(warehouse):
    result = warehouse.run_query(
        f"SELECT exchange, symbol FROM {GOLD_TABLE}",
        max_rows=5,
    )

    assert result.columns == ["exchange", "symbol"]
    assert len(result.rows) == 5
    assert result.truncated is True

    columns = warehouse.describe_table(GOLD_TABLE)
    names = [column.name for column in columns]

    assert "exchange" in names
    assert "symbol" in names
    assert "rate_per_8h" in names


@pytest.mark.parametrize(
    "query",
    [
        "SELECT * FROM funding_regime_project.bronze.raw_funding_rates LIMIT 1",
        "SELECT * FROM funding_regime_project.silver.funding_rates LIMIT 1",
        f"INSERT INTO {GOLD_TABLE} SELECT * FROM {GOLD_TABLE} WHERE 1 = 0",
        f"DELETE FROM {GOLD_TABLE} WHERE 1 = 0",
    ],
)

def test_forbidden_operations_are_denied(warehouse, query):
    with pytest.raises(PermissionDeniedError):
        warehouse.run_query(query)
