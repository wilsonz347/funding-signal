# src/agent/warehouse.py
"""Database access layer"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Protocol

from databricks import sql
from databricks.sdk.core import Config, oauth_service_principal

from src.agent.settings import Settings


# Error class
class WarehouseError(Exception):
    """Base error for anything that goes wrong talking to the warehouse."""
    pass

class PermissionDeniedError(WarehouseError):
    """The credential is not allowed to do this."""
    pass


# Types class
@dataclass(frozen=True)
class ColumnInfo:
    name: str
    data_type: str
    comment: str | None = None

@dataclass
class QueryResult:
    columns: list[str]
    rows: list[dict[str, Any]]
    truncated: bool
    duration_ms: float


# Interface Class
class Warehouse(Protocol):
    """What the rest of the codebase depends on. Real class and test fakes both satisfy it."""

    def run_query(self, sql: str, max_rows: int = 50) -> QueryResult: ...
    def describe_table(self, full_name: str) -> list[ColumnInfo]: ...
    def close(self) -> None: ...


# Helpers
def apply_cap(rows: list[Any], max_rows: int) -> tuple[list[Any], bool]:
    """Given up to max_rows + 1 fetched rows, return (rows capped to max_rows, truncated flag)."""
    if len(rows) <= max_rows:
        return rows, False
    return rows[:max_rows], True

def parse_describe(raw_rows: list[dict[str, Any]]) -> list[ColumnInfo]:
    """Turn raw DESCRIBE TABLE rows into ColumnInfo.

    Stop at the first row with an empty col_name or one starting with '#'
    (partition / detail sections follow the column list).
    """
    columns: list[ColumnInfo] = []
    for row in raw_rows:
        col_name = row["col_name"]
        if not col_name or col_name.startswith("#"):
            break
        columns.append(ColumnInfo(
            name=col_name,
            data_type=row["data_type"],
            comment=row.get("comment"),
        ))
    return columns


def translate_error(exc: Exception) -> WarehouseError:
    """Map connector exceptions to application-level error types."""
    message = str(exc)
    normalized = message.casefold()

    permission_markers = (
        "permission denied",
        "permission_denied",
        "insufficient_permissions",
        "insufficient privileges",
        "does not have permission",
        "does not have the privilege",
        "not authorized",
        "unauthorized",
    )

    if any(marker in normalized for marker in permission_markers):
        return PermissionDeniedError(message)

    return WarehouseError(message)


# Implementation class
class DatabricksWarehouse:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._conn = None

    def _credentials_provider(self):
        return oauth_service_principal(
            Config(
                host=f"https://{self._settings.host}",
                client_id=self._settings.client_id,
                client_secret=self._settings.client_secret,
            )
        )

    def _connection(self):
        """Create the connection on first use, then reuse it."""
        if self._conn is None:
            self._conn = sql.connect(
                server_hostname=self._settings.host,
                http_path=self._settings.http_path,
                credentials_provider=self._credentials_provider,
            )
        return self._conn

    
    def run_query(self, sql_text: str, max_rows: int = 50) -> QueryResult:
        if max_rows < 1:
            raise ValueError("max_rows must be at least 1")

        start = time.perf_counter()

        try:
            with self._connection().cursor() as cursor:
                cursor.execute(sql_text)

                if cursor.description is None:
                    raise WarehouseError("Query did not return a result set")

                columns = [col[0] for col in cursor.description]
                raw_rows = cursor.fetchmany(max_rows + 1)

                raw_rows, truncated = apply_cap(raw_rows, max_rows)

                rows = [
                    dict(zip(columns, row))
                    for row in raw_rows
                ]

            return QueryResult(
                columns=columns,
                rows=rows,
                truncated=truncated,
                duration_ms=(time.perf_counter() - start) * 1000,
            )

        except WarehouseError:
            raise

        except Exception as exc:
            raise translate_error(exc) from exc
    
    def describe_table(self, full_name: str) -> list[ColumnInfo]:
        result = self.run_query(
            f"DESCRIBE TABLE {full_name}",
            max_rows=1000,
        )
        return parse_describe(result.rows)

    def close(self) -> None:
        connection = self._conn
        if connection is not None:
            connection.close()
            self._conn = None

    def __enter__(self) -> "DatabricksWarehouse":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
