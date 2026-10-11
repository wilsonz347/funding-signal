# tests/test_answer.py
"""Unit tests for the Answerer class in src/agent/answer.py"""

import pytest

from src.agent.agent import AgentResult
from src.agent.answer import Answerer
from src.agent.catalog import load_catalog
from src.agent.llm import LLMError
from src.agent.warehouse import QueryResult


class FakeLLM:
    def __init__(self, response="Exchange A has the higher average funding rate."):
        self.response = response
        self.calls = []

    def complete(self, system, prompt):
        self.calls.append((system, prompt))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


@pytest.fixture
def catalog():
    return load_catalog("config/agent_catalog.yaml")


@pytest.fixture
def query_result():
    return QueryResult(
        columns=["exchange", "avg_rate"],
        rows=[
            {"exchange": "Exchange A", "avg_rate": 0.0001},
            {"exchange": "Exchange B", "avg_rate": 0.0002},
        ],
        truncated=False,
        duration_ms=100,
    )


def test_successful_answer(catalog, query_result):
    llm = FakeLLM()
    answerer = Answerer(llm, catalog)

    result = AgentResult(
        question="What is the average funding rate by exchange?",
        ok=True,
        sql="SELECT exchange, AVG(rate_per_8h) AS avg_rate FROM funding_regime_project.gold.funding_rate_analysis GROUP BY exchange",
        result=query_result,
    )

    answer = answerer.answer(result)

    assert answer.ok
    assert answer.text == llm.response
    assert answer.rows_shown == 2
    assert answer.rows_total == 2
    assert "Exchange A" in llm.calls[0][1]
    assert "0.0001" in llm.calls[0][1]


def test_empty_results_skip_llm(catalog):
    llm = FakeLLM()
    answerer = Answerer(llm, catalog)

    result = AgentResult(
        question="Find frozen funding rates",
        ok=True,
        result=QueryResult([], [], False, 50),
    )

    answer = answerer.answer(result)

    assert answer.text == "No rows matched the query."
    assert not llm.calls


def test_failed_query_skips_llm(catalog):
    llm = FakeLLM()
    answerer = Answerer(llm, catalog)

    result = AgentResult(
        question="Find frozen funding rates",
        ok=False,
        error="Warehouse error",
    )

    answer = answerer.answer(result)

    assert answer.text == "Warehouse error"
    assert not llm.calls


def test_llm_failure_returns_fallback(catalog, query_result):
    llm = FakeLLM(LLMError("Ollama unavailable"))
    answerer = Answerer(llm, catalog)

    result = AgentResult(
        question="What is the average funding rate by exchange?",
        ok=True,
        sql="SELECT ...",
        result=query_result,
    )

    answer = answerer.answer(result)

    assert answer.ok
    assert "summary is unavailable" in answer.text
    assert answer.rows_shown == 2
