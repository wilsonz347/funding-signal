# src/agent/agent.py
"""SQL agent loop: generate -> validate -> execute, with bounded retries"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.agent.catalog import Catalog
from src.agent.llm import LLMError, LLMClient
from src.agent.prompts import build_sql_prompt, extract_sql
from src.agent.sql_validator import SQLValidator
from src.agent.warehouse import (
    PermissionDeniedError,
    QueryResult,
    Warehouse,
    WarehouseError,
)


@dataclass
class Attempt:
    number: int
    stage: str = "generate"
    raw_reply: str | None = None
    extracted_sql: str | None = None
    executed_sql: str | None = None
    errors: list[str] = field(default_factory=list)


@dataclass
class AgentResult:
    question: str
    ok: bool
    sql: str | None = None
    result: QueryResult | None = None
    attempts: list[Attempt] = field(default_factory=list)
    error: str | None = None


@dataclass
class SQLAgent:
    llm: LLMClient
    warehouse: Warehouse
    catalog: Catalog
    max_attempts: int = 3
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)

    def run(self, question: str) -> AgentResult:
        attempts: list[Attempt] = []
        previous_sql = None
        previous_errors = None

        validator = SQLValidator(self.catalog)

        for number in range(1, self.max_attempts + 1):
            attempt = Attempt(number=number)
            attempts.append(attempt)

            try:
                system, user = build_sql_prompt(
                    question=question,
                    catalog=self.catalog,
                    now=self.clock(),
                    previous_sql=previous_sql,
                    errors=previous_errors,
                )

                attempt.raw_reply = self.llm.complete(system, user)

            except LLMError as e:
                attempt.errors.append(f"LLM error: {e}")
                return AgentResult(
                    question=question,
                    ok=False,
                    attempts=attempts,
                    error=attempt.errors[-1],
                )

            attempt.stage = "extract"
            attempt.extracted_sql = extract_sql(attempt.raw_reply)

            validation = validator.validate(attempt.extracted_sql)

            if not validation.ok:
                attempt.stage = "validate"
                attempt.errors.extend(validation.errors)
                previous_sql = attempt.extracted_sql
                previous_errors = attempt.errors.copy()
                continue

            # Only execute the validator's normalized, capped SQL.
            attempt.stage = "execute"
            attempt.executed_sql = validation.sql

            try:
                result = self.warehouse.run_query(
                    validation.sql,
                    max_rows=self.catalog.max_query_rows,
                )

                attempt.stage = "success"
                return AgentResult(
                    question=question,
                    ok=True,
                    sql=validation.sql,
                    result=result,
                    attempts=attempts,
                )

            except PermissionDeniedError as e:
                attempt.errors.append(f"Permission denied: {e}")
                return AgentResult(
                    question=question,
                    ok=False,
                    attempts=attempts,
                    error=attempt.errors[-1],
                )

            except WarehouseError as e:
                attempt.errors.append(f"Warehouse error: {e}")
                previous_sql = attempt.executed_sql
                previous_errors = attempt.errors.copy()

        return AgentResult(
            question=question,
            ok=False,
            attempts=attempts,
            error=f"Query failed after {self.max_attempts} attempts.",
        )
