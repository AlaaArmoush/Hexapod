from __future__ import annotations

from typing import Any

import requests


DEFAULT_BASE_URL = "http://127.0.0.1:8080"
DEFAULT_START_COMMAND = (
    "llama-server -m ~/models/gemma4/google_gemma-4-E2B-it-Q4_K_M.gguf "
    "-c 2048 --reasoning off --temp 0 --top-k 1 --top-p 1 "
    "--n-predict 60 -t 4 -tb 4 --cache-reuse 256 "
    "--flash-attn on --mlock --host 127.0.0.1 --port 8080"
)


class LlamaClient:
    def __init__(self, base_url: str = DEFAULT_BASE_URL, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def chat(
        self,
        messages: list[dict[str, Any]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        json_object: bool = False,
    ) -> str:
        payload: dict[str, Any] = {"messages": messages}
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if json_object:
            payload["response_format"] = {"type": "json_object"}

        url = f"{self.base_url}/v1/chat/completions"
        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
        except requests.exceptions.Timeout as exc:
            raise TimeoutError(
                f"Timed out waiting for llama-server at {self.base_url} after "
                f"{self.timeout} seconds. The server is reachable, but generation "
                "did not finish before the client timeout."
            ) from exc
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

    def warmup(self, system_prompt: str) -> None:
        try:
            self.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": "hi"},
                ],
                temperature=0,
                max_tokens=1,
            )
        except Exception:
            pass  # warmup failure is non-fatal

    def _connection_help(self) -> str:
        return (
            f"Could not connect to llama-server at {self.base_url}.\n"
            "Please start it with:\n"
            f"  {DEFAULT_START_COMMAND}"
        )
