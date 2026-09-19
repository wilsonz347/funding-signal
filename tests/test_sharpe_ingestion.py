"""
Tests for src/ingestion/sharpe_client.py and sharpe_wrapper.py.

These never make a real HTTP call. requests.get and time.sleep are mocked,
so the tests run instantly and cost nothing against the real API quota.
"""

import requests
import pytest

from src.ingestion.sharpe_client import fetch_current_funding_rates, SharpeAPIError
from src.ingestion.sharpe_wrapper import fetch_current_funding_rates_safe

FAKE_KEY = "fake_api_key"


class FakeResponse:
    """Stand-in for requests.Response."""

    def __init__(self, status_code, text="{}", headers=None, url="https://fake.url"):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}
        self.url = url


# ---------- sharpe_client.fetch_current_funding_rates ----------

def test_fetch_success_returns_wrapped_metadata(monkeypatch):
    fake = FakeResponse(status_code=200, text='{"data": []}', headers={"X-RateLimit-Remaining": "29"})
    monkeypatch.setattr(requests, "get", lambda *a, **k: fake)

    result = fetch_current_funding_rates(FAKE_KEY)

    assert result["status_code"] == 200
    assert result["payload"] == '{"data": []}'
    assert result["headers"]["X-RateLimit-Remaining"] == "29"
    assert "fetched_at" in result


def test_fetch_network_error_raises_sharpe_api_error(monkeypatch):
    def raise_connection_error(*a, **k):
        raise requests.ConnectionError("boom")

    monkeypatch.setattr(requests, "get", raise_connection_error)

    with pytest.raises(SharpeAPIError):
        fetch_current_funding_rates(FAKE_KEY)


def test_fetch_does_not_alter_payload(monkeypatch):
    """Bronze principle: payload must pass through completely unmodified."""
    raw_payload = '{"data": [{"exchange": "Binance", "symbol": "BTCUSDT", "rate": 6.897e-05}]}'
    fake = FakeResponse(status_code=200, text=raw_payload)
    monkeypatch.setattr(requests, "get", lambda *a, **k: fake)

    result = fetch_current_funding_rates(FAKE_KEY)

    assert result["payload"] == raw_payload


# ---------- sharpe_wrapper.fetch_current_funding_rates_safe ----------

def test_wrapper_success_on_first_try(monkeypatch):
    fake = FakeResponse(status_code=200, text='{"data": []}')
    monkeypatch.setattr(requests, "get", lambda *a, **k: fake)

    outcome = fetch_current_funding_rates_safe(FAKE_KEY)

    assert outcome["success"] is True
    assert outcome["result"]["status_code"] == 200


def test_wrapper_network_error_returns_failure_without_raising(monkeypatch):
    def raise_connection_error(*a, **k):
        raise requests.ConnectionError("boom")

    monkeypatch.setattr(requests, "get", raise_connection_error)

    outcome = fetch_current_funding_rates_safe(FAKE_KEY)

    assert outcome["success"] is False
    assert "network_error" in outcome["reason"]


def test_wrapper_retries_on_429_then_succeeds(monkeypatch):
    responses = [
        FakeResponse(status_code=429, headers={"Retry-After": "0"}),
        FakeResponse(status_code=200, text='{"data": []}'),
    ]
    monkeypatch.setattr(requests, "get", lambda *a, **k: responses.pop(0))
    monkeypatch.setattr("src.ingestion.sharpe_wrapper.time.sleep", lambda seconds: None)

    outcome = fetch_current_funding_rates_safe(FAKE_KEY)

    assert outcome["success"] is True
    assert outcome["result"]["status_code"] == 200


def test_wrapper_exhausts_retries_on_persistent_429(monkeypatch):
    fake = FakeResponse(status_code=429, headers={"Retry-After": "0"})
    monkeypatch.setattr(requests, "get", lambda *a, **k: fake)
    monkeypatch.setattr("src.ingestion.sharpe_wrapper.time.sleep", lambda seconds: None)

    outcome = fetch_current_funding_rates_safe(FAKE_KEY)

    assert outcome["success"] is False
    assert outcome["reason"] == "rate_limit_or_quota_exceeded"


def test_wrapper_does_not_retry_on_unexpected_status(monkeypatch):
    call_count = {"n": 0}

    def fake_get(*a, **k):
        call_count["n"] += 1
        return FakeResponse(status_code=500, text="server error")

    monkeypatch.setattr(requests, "get", fake_get)

    outcome = fetch_current_funding_rates_safe(FAKE_KEY)

    assert outcome["success"] is False
    assert outcome["reason"] == "unexpected_status_500"
    assert call_count["n"] == 1  # confirms no retry happened on a non-429 failure
