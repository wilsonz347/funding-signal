# src/agent/catalog.py
"""Loads agent_catalog.yaml and provides access to its contents."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

class CatalogError(Exception):
    """The catalog file is missing or malformed."""

class Catalog:
    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data

    @property
    def allowed_tables(self) -> frozenset[str]:
        return frozenset(table["name"].lower() for table in self.data["tables"])

    @property
    def max_query_rows(self) -> int:
        return self.data["policies"]["max_query_rows"]

    @property
    def max_llm_rows(self) -> int:
        return self.data["policies"]["max_llm_rows"]

    @property
    def default_time_window_days(self) -> int:
        return self.data["policies"]["default_time_window_days"]

    def is_table_allowed(self, name: str) -> bool:
        return name.lower() in self.allowed_tables

    def table(self, name: str) -> dict[str, Any]:
        for table in self.data["tables"]:
            if table["name"].lower() == name.lower():
                return table
        raise CatalogError(f"Table {name} not found")

def load_catalog(path: str | Path) -> Catalog:
    file_path = Path(path)

    if not file_path.is_file():
        raise CatalogError(f"Catalog file not found: {file_path}")

    with open(file_path, "r") as f:
        try:
            data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise CatalogError(f"Error parsing catalog file: {e}")

    if not isinstance(data, dict) or "tables" not in data or "policies" not in data:
        raise CatalogError("Catalog file is malformed: missing 'tables' or 'policies'")

    return Catalog(data)
