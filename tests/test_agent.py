# tests/test_agent.py
"""Unit tests for the SQL agent"""

from datetime import datetime, timezone

import yaml

from src.agent.agent import SQLAgent
from src.agent.catalog import Catalog
from src.agent.llm import LLMError
from src.agent.warehouse import PermissionDeniedError, QueryResult, WarehouseError

T = "funding_regime_project.gold.funding_rate_analysis"
cat = Catalog(yaml.safe_load(open("config/agent_catalog.yaml")))
GOOD = f"```sql\nSELECT exchange, COUNT(*) AS n FROM {T} GROUP BY exchange ORDER BY n DESC\n```"
BAD = f"```sql\nSELECT secret FROM {T}\n```"
FIXED_NOW = datetime(2026, 10, 11, 14, 30, tzinfo=timezone.utc)
OK = QueryResult(["exchange", "n"], [{"exchange": "a", "n": 1}], False, 1.0)


class FakeLLM:
    """Scripted replies in order; records every prompt it receives."""
    def __init__(self, replies):
        self.replies, self.prompts = list(replies), []

    def complete(self, system, prompt):
        self.prompts.append(prompt)
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


class FakeWarehouse:
    def __init__(self, outcomes):
        self.outcomes, self.sqls = list(outcomes), []

    def run_query(self, sql, max_rows):
        self.sqls.append((sql, max_rows))
        o = self.outcomes.pop(0)
        if isinstance(o, Exception):
            raise o
        return o


def agent(llm, wh, **kw):
    return SQLAgent(llm, wh, cat, clock=lambda: FIXED_NOW, **kw)


def test_success_first_try():
    r = agent(FakeLLM([GOOD]), FakeWarehouse([OK])).run("q")
    assert r.ok and len(r.attempts) == 1 and r.attempts[0].stage == "success"


def test_validator_rejection_then_success_and_feedback_reaches_model():
    llm = FakeLLM([BAD, GOOD])
    r = agent(llm, FakeWarehouse([OK])).run("q")
    assert r.ok and len(r.attempts) == 2
    assert "does not exist" in llm.prompts[1] and "SELECT secret" in llm.prompts[1]


def test_databricks_error_then_success_shows_executed_sql():
    llm, wh = FakeLLM([GOOD, GOOD]), FakeWarehouse([WarehouseError("boom 42703"), OK])
    r = agent(llm, wh).run("q")
    assert r.ok and "boom 42703" in llm.prompts[1] and wh.sqls[0][0] in llm.prompts[1]


def test_all_attempts_fail():
    r = agent(FakeLLM([BAD] * 3), FakeWarehouse([])).run("q")
    assert not r.ok and len(r.attempts) == 3 and "3 attempts" in r.error


def test_permission_denied_stops_immediately():
    r = agent(FakeLLM([GOOD, GOOD]), FakeWarehouse([PermissionDeniedError("nope")])).run("q")
    assert not r.ok and len(r.attempts) == 1 and "Permission" in r.error


def test_llm_error_stops_immediately():
    r = agent(FakeLLM([LLMError("down")]), FakeWarehouse([])).run("q")
    assert not r.ok and len(r.attempts) == 1 and "LLM error" in r.error


def test_executes_normalized_capped_sql_not_raw():
    wh = FakeWarehouse([OK])
    agent(FakeLLM([f"```sql\nSELECT exchange FROM {T}\n```"]), wh).run("q")
    sql, max_rows = wh.sqls[0]
    assert sql.endswith("LIMIT 10000") and max_rows == 10000


def test_default_clock_works():
    assert SQLAgent(FakeLLM([GOOD]), FakeWarehouse([OK]), cat).run("q").ok


def test_stale_errors_do_not_leak_between_attempts():
    llm = FakeLLM([BAD, GOOD, GOOD])
    agent(llm, FakeWarehouse([WarehouseError("db err"), OK])).run("q")
    assert "does not exist" not in llm.prompts[2] and "db err" in llm.prompts[2]
