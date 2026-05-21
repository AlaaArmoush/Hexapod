"""Client for llama-server's OpenAI-compatible chat endpoint."""

from __future__ import annotations

from typing import Any

import requests


DEFAULT_BASE_URL = "http://127.0.0.1:8080"
DEFAULT_START_COMMAND = (
    "llama-server -m ~/models/gemma4/gemma-4-E2B-it-Q8_0.gguf "
    "-c 2048 --host 127.0.0.1 --port 8080"
)


class LlamaClient:
    """Small wrapper around llama-server's `/v1/chat/completions` endpoint."""

    def __init__(self, base_url: str = DEFAULT_BASE_URL, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def chat(
        self,
        messages: list[dict[str, Any]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Send chat messages to llama-server and return the assistant text."""

        payload: dict[str, Any] = {"messages": messages}
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        url = f"{self.base_url}/v1/chat/completions"
        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
        except requests.exceptions.RequestException as exc:
            raise ConnectionError(self._connection_help()) from exc

        if response.status_code != 200:
            raise RuntimeError(
                f"llama-server returned HTTP {response.status_code}: {response.text}"
            )

        try:
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise RuntimeError("llama-server returned an unexpected response shape") from exc

    def _connection_help(self) -> str:
        return (
            f"Could not connect to llama-server at {self.base_url}.\n"
            "Please start it with:\n"
            f"  {DEFAULT_START_COMMAND}"
        )

