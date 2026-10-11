# tests/test_llm.py
"""Unit tests for the Ollama LLM client"""

from unittest.mock import Mock, patch

import httpx
import pytest

from src.agent.llm import LLMError, OllamaClient


@pytest.fixture
def client():
    return OllamaClient(
        base_url="http://localhost:11434",
        model="qwen2.5-coder:7b",
        timeout=30.0,
        context_window=8192,
    )


def mock_response(content: str = "SELECT 1") -> Mock:
    response = Mock()
    response.json.return_value = {
        "message": {"content": content}
    }
    response.raise_for_status.return_value = None
    return response


def test_complete_returns_model_response(client):
    with patch(
        "src.agent.llm.httpx.post",
        return_value=mock_response("SELECT 1"),
    ) as mock_post:
        result = client.complete("Generate SQL.", "Return SELECT 1.")

    assert result == "SELECT 1"
    mock_post.assert_called_once()


def test_complete_sends_expected_request(client):
    with patch(
        "src.agent.llm.httpx.post",
        return_value=mock_response(),
    ) as mock_post:
        client.complete("System instructions", "User question")

    args, kwargs = mock_post.call_args

    assert args[0] == "http://localhost:11434/api/chat"
    assert kwargs["timeout"] == 30.0
    assert kwargs["json"] == {
        "model": "qwen2.5-coder:7b",
        "stream": False,
        "messages": [
            {"role": "system", "content": "System instructions"},
            {"role": "user", "content": "User question"},
        ],
        "options": {
            "temperature": 0,
            "num_ctx": 8192,
        },
    }


def test_complete_strips_whitespace(client):
    with patch(
        "src.agent.llm.httpx.post",
        return_value=mock_response("  SELECT 1  \n"),
    ):
        result = client.complete("System", "Question")

    assert result == "SELECT 1"


@pytest.mark.parametrize("content", ["", "   ", "\n"])
def test_complete_rejects_empty_response(client, content):
    with patch(
        "src.agent.llm.httpx.post",
        return_value=mock_response(content),
    ):
        with pytest.raises(LLMError, match="empty response"):
            client.complete("System", "Question")


@pytest.mark.parametrize(
    "error",
    [
        httpx.ConnectError("Connection refused"),
        httpx.TimeoutException("Request timed out"),
        httpx.HTTPStatusError(
            "Server error",
            request=httpx.Request("POST", "http://localhost:11434/api/chat"),
            response=httpx.Response(
                500,
                request=httpx.Request(
                    "POST", "http://localhost:11434/api/chat"
                ),
            ),
        ),
    ],
)
def test_complete_wraps_http_errors(client, error):
    with patch(
        "src.agent.llm.httpx.post",
        side_effect=error,
    ):
        with pytest.raises(LLMError):
            client.complete("System", "Question")


def test_complete_rejects_invalid_json(client):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.side_effect = ValueError("Invalid JSON")

    with patch("src.agent.llm.httpx.post", return_value=response):
        with pytest.raises(LLMError):
            client.complete("System", "Question")


def test_complete_rejects_missing_message_content(client):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"message": {}}

    with patch("src.agent.llm.httpx.post", return_value=response):
        with pytest.raises(LLMError):
            client.complete("System", "Question")
