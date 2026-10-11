# tests/test_catalog.py
"""
Tests for src/agent/catalog.py.
Uses the real agent_catalog.yaml (frozen as a fixture).
"""
from pathlib import Path
import pytest
from src.agent.catalog import CatalogError, load_catalog

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = PROJECT_ROOT / "config" / "agent_catalog.yaml"

GOLD_TABLE = "funding_regime_project.gold.funding_rate_analysis"

def test_load_real_catalog():
    catalog = load_catalog(CATALOG_PATH)

    assert GOLD_TABLE in catalog.allowed_tables
    assert catalog.max_query_rows == 10000
    assert catalog.max_llm_rows == 50

def test_missing_file_raises_catalog_error(tmp_path):
    missing_path = tmp_path / "missing.yaml"

    with pytest.raises(CatalogError, match="not found"):
        load_catalog(missing_path)

def test_catalog_without_tables_raises_catalog_error(tmp_path):
    catalog_path = tmp_path / "invalid.yaml"
    catalog_path.write_text(
        "policies:\n"
        "  max_query_rows: 10000\n"
        "  max_llm_rows: 50\n",
        encoding="utf-8",
    )

    with pytest.raises(CatalogError, match="tables"):
        load_catalog(catalog_path)
