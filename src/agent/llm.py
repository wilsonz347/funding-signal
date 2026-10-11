# src/agent/llm.py
"""LLM access layer"""

from __future__ import annotations
from typing import Protocol
from dataclasses import dataclass
import httpx


class LLMError(Exception):
    """The model could not be reached or returned something unusable."""

class LLMClient(Protocol):
    def complete(self, system: str, prompt: str) -> str: ...


@dataclass
class OllamaClient:
    base_url: str = "http://localhost:11434"
    model: str = "qwen2.5-coder:7b"
    timeout: float = 120.0
    context_window: int = 8192

    def complete(self, system: str, prompt: str) -> str:
        # Initialize the payload for the Ollama API request
        payload = {
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "options": {
                "temperature": 0,
                "num_ctx": self.context_window,
            },
        }
        
        try:
            # Send the request to the Ollama API
            response = httpx.post(f"{self.base_url}/api/chat", json=payload, timeout=self.timeout)
            response.raise_for_status()

            # Parse the response JSON and extract the text
            data = response.json()
            text = data["message"]["content"].strip()

        except httpx.RequestError as e:
            raise LLMError(f"Request error: {e}") from e
        except httpx.HTTPStatusError as e:
            raise LLMError(f"HTTP error: {e.response.status_code} - {e.response.text}") from e
        except (KeyError, ValueError) as e:
            raise LLMError(f"Invalid response format: {e}") from e

        if not text:
            raise LLMError("Model returned an empty response")

        return text
    