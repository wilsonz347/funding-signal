# tests/test_prompts.py
"""Tests for prompt construction and sql parsing"""

from datetime import datetime, timezone

import pytest

from src.agent.catalog import Catalog
from src.agent.prompts import (
    build_sql_prompt,
    extract_sql,
    render_catalog,
)


@pytest.fixture
def catalog():
    """Catalog fixture for prompt unit tests"""
    return Catalog(
        {
            "tables": [
                {
                    "name": "funding_regime_project.gold.funding_rate_analysis",
                    "purpose": "Funding-rate analytics.",
                    "description": "One row per exchange, symbol, and poll timestamp.",
                    "grain": ["exchange", "symbol", "fetched_at"],
                    "columns": {
                        "exchange": {
                            "type": "string",
                            "role": "dimension",
                            "description": "Exchange where the contract trades.",
                        },
                        "symbol": {
                            "type": "string",
                            "role": "dimension",
                            "description": "Exchange-specific contract symbol.",
                        },
                        "margin_type": {
                            "type": "string",
                            "role": "dimension",
                            "values": ["linear", "inverse"],
                            "description": "Contract margin type.",
                        },
                        "fetched_at": {
                            "type": "timestamp",
                            "role": "time",
                            "description": "UTC observation timestamp.",
                        },
                        "rate_per_8h": {
                            "type": "double",
                            "role": "measure",
                            "unit": "decimal_fraction",
                            "description": "Funding rate normalized to eight hours.",
                        },
                        "funding_change": {
                            "type": "double",
                            "role": "measure",
                            "nullable": True,
                            "description": "Poll-to-poll funding-rate change.",
                        },
                    },
                }
            ],
            "policies": {
                "max_query_rows": 10000,
                "max_llm_rows": 50,
                "default_time_window_days": 30,
                "read_only": True,
                "allowed_tables_only": True,
                "allowed_columns_only": True,
                "prefer_aggregation": True,
            },
        }
    )


@pytest.fixture
def now():
    return datetime(2026, 10, 11, 12, 0, 0, tzinfo=timezone.utc)


# render_catalog
def test_render_catalog_includes_table_metadata(catalog):
    rendered = render_catalog(catalog)

    assert "funding_regime_project.gold.funding_rate_analysis" in rendered
    assert "Funding-rate analytics." in rendered
    assert "exchange, symbol, fetched_at" in rendered


def test_render_catalog_includes_column_metadata(catalog):
    rendered = render_catalog(catalog)

    assert "rate_per_8h" in rendered
    assert "double" in rendered
    assert "measure" in rendered
    assert "unit=decimal_fraction" in rendered
    assert "nullable" in rendered


def test_render_catalog_includes_allowed_values(catalog):
    rendered = render_catalog(catalog)

    assert "allowed values: linear, inverse" in rendered


# build_sql_prompt
def test_build_sql_prompt_includes_catalog_and_policies(catalog, now):
    question = "What is the average funding rate by exchange?"

    system, user = build_sql_prompt(question, catalog, now)

    assert "funding_regime_project.gold.funding_rate_analysis" in system
    assert "last 30 days" in system
    assert "LIMIT no greater than 50" in system
    assert "rate_per_8h" in system
    assert "margin_type" in system

    assert question in user
    assert "2026-10-11 12:00:00 UTC" in user


def test_build_sql_prompt_includes_examples(catalog, now):
    system, _ = build_sql_prompt("Show funding rates", catalog, now)

    assert "AVG(rate_per_8h)" in system
    assert "ROW_NUMBER() OVER" in system
    assert "PARTITION BY exchange, symbol" in system


def test_build_sql_prompt_includes_repair_context(catalog, now):
    previous_sql = "SELECT invalid_column FROM invalid_table"
    errors = [
        "Column 'invalid_column' is not allowed",
        "Table 'invalid_table' is not allowed",
    ]

    _, user = build_sql_prompt(
        "Show funding rates",
        catalog,
        now,
        previous_sql=previous_sql,
        errors=errors,
    )

    assert previous_sql in user
    assert errors[0] in user
    assert errors[1] in user
    assert "Fix the query" in user


def test_build_sql_prompt_without_errors_has_no_repair_section(catalog, now):
    _, user = build_sql_prompt(
        "Show funding rates",
        catalog,
        now,
        previous_sql="SELECT invalid_column",
        errors=None,
    )

    assert "previous SQL was rejected" not in user


# extract_sql
def test_extract_sql_from_sql_fence():
    reply = "```sql\nSELECT exchange FROM funding_table LIMIT 10\n```"

    assert extract_sql(reply) == (
        "SELECT exchange FROM funding_table LIMIT 10"
    )


def test_extract_sql_from_unlabeled_fence():
    reply = "```\nSELECT 1\n```"

    assert extract_sql(reply) == "SELECT 1"


def test_extract_sql_ignores_text_outside_fence():
    reply = (
        "Here is the query:\n"
        "```sql\nSELECT 1\n```\n"
        "That is the result."
    )

    assert extract_sql(reply) == "SELECT 1"


def test_extract_sql_returns_unfenced_reply():
    reply = "  SELECT exchange FROM funding_table LIMIT 10  "

    assert extract_sql(reply) == (
        "SELECT exchange FROM funding_table LIMIT 10"
    )


def test_extract_sql_handles_empty_reply():
    assert extract_sql("") == ""
    assert extract_sql("   ") == ""
