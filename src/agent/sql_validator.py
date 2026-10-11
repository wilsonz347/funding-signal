# src/agent/sql_validator.py
"""Validates SQL queries against the catalog and policies."""
from __future__ import annotations

from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from src.agent.catalog import Catalog

DIALECT = "databricks"

@dataclass
class ValidationResult:
    ok: bool
    sql: str | None = None
    errors: list[str] = field(default_factory=list)


@dataclass
class SQLValidator:
    catalog: Catalog

    def validate(self, sql: str) -> ValidationResult:
        if not sql or not sql.strip():
            return ValidationResult(False, errors=["SQL query is empty."])

        # Require exactly one statement
        try:
            statements = [s for s in sqlglot.parse(sql, read=DIALECT) if s is not None]
        except SqlglotError as e:
            return ValidationResult(False, errors=[f"Invalid SQL: {e}"])
        if len(statements) != 1:
            return ValidationResult(False, errors=["Exactly one statement is allowed."])

        # Allow only plain SELECT queries
        root = statements[0]
        if not isinstance(root, exp.Select) or root.args.get("into"):
            return ValidationResult(False, errors=["Only SELECT queries are allowed."])

        # Validate table access
        cte_names = {c.alias_or_name.lower() for c in root.find_all(exp.CTE)}
        table_names, errors = [], []
        for table in root.find_all(exp.Table):
            if not isinstance(table.this, exp.Identifier):  # e.g. read_files('s3://...')
                errors.append("Table functions are not allowed.")
                continue
            if not table.db and table.name.lower() in cte_names:
                continue
            full_name = ".".join(p for p in (table.catalog, table.db, table.name) if p).lower()
            if not self.catalog.is_table_allowed(full_name):
                errors.append(f"Table '{full_name}' is not allowed (use the full catalog.schema.table name).")
            else:
                table_names.append(full_name)
        if errors:
            return ValidationResult(False, errors=sorted(set(errors)))

        # One physical table is allowed
        table_names = sorted(set(table_names))
        if len(table_names) != 1:
            return ValidationResult(False, errors=["Query must reference exactly one approved table."])

        # Validate columns: must exist in the catalog, or be an alias the query defines itself
        allowed_columns = {name.lower() for name in self.catalog.table(table_names[0])["columns"]}
        aliases = {a.alias.lower() for a in root.find_all(exp.Alias) if a.alias} 
        for column in root.find_all(exp.Column):
            if column.is_star:
                continue
            name = column.name.lower()
            if name not in allowed_columns and name not in aliases:
                errors.append(f"Column '{column.name}' does not exist. Available columns: {', '.join(sorted(allowed_columns))}.")
        if errors:
            return ValidationResult(False, errors=sorted(set(errors)))

        return ValidationResult(True, sql=self._cap_limit(root).sql(dialect=DIALECT))

    def _cap_limit(self, root: exp.Select) -> exp.Select:
        max_rows = self.catalog.max_query_rows
        limit = root.args.get("limit")
        value = limit.expression if limit is not None else None
        # Only a plain integer literal can be trusted
        if not (isinstance(value, exp.Literal) and value.is_int) or int(value.name) > max_rows:
            return root.limit(max_rows)
        return root


def check_query_quality(sql: str) -> list[str]:
    """Check query quality separately from security validation"""
    try:
        root = sqlglot.parse_one(sql, read=DIALECT)
    except SqlglotError:
        return []

    if not isinstance(root, exp.Select):
        return []

    if root.args.get("limit") is not None and root.args.get("order") is None:
        return [
            "Query uses LIMIT without ORDER BY. Add an ORDER BY clause "
            "to ensure the returned rows have a meaningful order."
        ]

    return []