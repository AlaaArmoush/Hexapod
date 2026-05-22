"""Core local agent loop: model output to validated action."""

from __future__ import annotations

import json
from typing import Any, Callable

from .agent_errors import AgentPlanError
from .agent_plan import parse_agent_plan
from .agent_validator import validate_agent_plan
from .prompts import SYSTEM_PROMPT
from .tool_executor import execute_tools


MOCK_LLM_RESPONSE = json.dumps(
    {
        "version": 1,
        "kind": "final_response",
        "response": {
            "speak": "Mock mode active.",
            "emotion": "neutral",
            "face": "idle",
        },
    }
)


class AgentLoop:
    def __init__(
        self,
        llama_client: Any | None = None,
        tool_executor: Callable[[list[dict[str, Any]]], list[dict[str, Any]]] = execute_tools,
        mock_llm: bool = False,
        verbose: bool = False,
        enable_tools: bool = True,
        summarize_tool_results: bool = False,
    ):
        self.llama_client = llama_client
        self.tool_executor = tool_executor
        self.mock_llm = mock_llm
        self.verbose = verbose
        self.enable_tools = enable_tools
        self.summarize_tool_results = summarize_tool_results

    def run_once(self, user_input: str) -> dict[str, Any]:
        """Run one user turn through the model, parser, validator, and tools."""

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_input},
        ]

        try:
            raw_output = self._chat(messages)
            if self.verbose:
                print("raw_model_output:")
                print(raw_output)

            plan = parse_agent_plan(raw_output)
        except AgentPlanError as exc:
            return {
                "ok": False,
                "kind": "error",
                "speak": "I could not understand the model response safely.",
                "error": str(exc),
                "tool_results": [],
                "raw_model_output": raw_output if "raw_output" in locals() else "",
            }
        except Exception as exc:
            return {
                "ok": False,
                "kind": "error",
                "speak": "I could not complete that request.",
                "error": str(exc),
                "tool_results": [],
                "raw_model_output": "",
            }

        return self._run_plan(raw_output=raw_output, plan=plan)

    def _run_plan(
        self,
        plan: dict[str, Any],
        raw_output: str,
    ) -> dict[str, Any]:
        try:
            validated = validate_agent_plan(plan)
        except AgentPlanError as exc:
            return {
                "ok": False,
                "kind": "error",
                "speak": "I could not understand the model response safely.",
                "error": str(exc),
                "tool_results": [],
                "raw_model_output": raw_output,
            }

        tool_results: list[dict[str, Any]] = []
        if validated.kind in {"tool_request", "mixed_request"}:
            if self.enable_tools:
                tool_results = self.tool_executor(validated.tools)
                if self.summarize_tool_results:
                    tool_results = self._summarize_tool_results(tool_results)
            else:
                tool_results = [
                    {
                        "ok": False,
                        "name": tool.get("name", "unknown"),
                        "spoken_text": "Tool execution is disabled.",
                        "data": {"args": tool.get("args", {})},
                        "display_face": "thinking",
                        "error": "tools_disabled",
                    }
                    for tool in validated.tools
                ]

        return {
            "ok": True,
            "kind": validated.kind,
            "speak": validated.speak,
            "emotion": validated.emotion,
            "face": validated.face,
            "tool_results": tool_results,
            "raw_model_output": raw_output,
        }

    def _chat(self, messages: list[dict[str, str]]) -> str:
        if self.mock_llm:
            return MOCK_LLM_RESPONSE
        if self.llama_client is None:
            raise RuntimeError("A llama client is required unless mock_llm is enabled.")
        return self.llama_client.chat(messages)

    def _summarize_tool_results(
        self, tool_results: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        summarized = []
        for result in tool_results:
            updated = dict(result)
            if not result.get("ok"):
                summarized.append(updated)
                continue

            try:
                summary = self._chat(
                    [
                        {
                            "role": "system",
                            "content": (
                                "Summarize tool output for a robot assistant. "
                                "Use only the provided tool result. "
                                "If the result is insufficient, say so. "
                                "Reply with one short sentence and no markdown."
                            ),
                        },
                        {
                            "role": "user",
                            "content": "The tool returned: {}".format(
                                json.dumps(result, sort_keys=True)
                            ),
                        },
                    ]
                ).strip()
            except Exception:
                summarized.append(updated)
                continue

            if summary:
                updated["spoken_text"] = summary
                updated["summarized"] = True
            summarized.append(updated)

        return summarized
