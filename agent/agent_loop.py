"""Core local agent loop: model output to validated action."""

from __future__ import annotations

import json
import time
from typing import Any, Callable

from .agent_errors import AgentPlanError
from .agent_plan import parse_agent_plan
from .agent_validator import validate_agent_plan
from .fast_robot_intent import build_fast_robot_plan
from .prompts import RUNTIME_SYSTEM_PROMPT, build_prompt
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
        system_prompt: str | None = RUNTIME_SYSTEM_PROMPT,
        temperature: float | None = 0,
        max_tokens: int | None = 80,
        summarizer_max_tokens: int | None = 80,
        json_response_format: bool = False,
        fast_robot_shortcuts: bool = True,
    ):
        self.llama_client = llama_client
        self.tool_executor = tool_executor
        self.mock_llm = mock_llm
        self.verbose = verbose
        self.enable_tools = enable_tools
        self.summarize_tool_results = summarize_tool_results
        self._use_dynamic_prompt = system_prompt is None
        self.system_prompt = system_prompt or RUNTIME_SYSTEM_PROMPT
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.summarizer_max_tokens = summarizer_max_tokens
        self.json_response_format = json_response_format
        self.fast_robot_shortcuts = fast_robot_shortcuts

    def run_once(self, user_input: str) -> dict[str, Any]:
        """Run one user turn through the model, parser, validator, and tools."""

        started_at = time.perf_counter()
        timings: dict[str, Any] = {}

        prompt = build_prompt(user_input) if self._use_dynamic_prompt else self.system_prompt
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_input},
        ]

        try:
            if self.fast_robot_shortcuts:
                fast_plan = build_fast_robot_plan(user_input)
                if fast_plan is not None:
                    raw_output = json.dumps(fast_plan, separators=(",", ":"))
                    timings["plan_source"] = "fast_robot"
                    if self.verbose:
                        print("fast_robot_shortcut: true")
                        print("raw_model_output:")
                        print(raw_output)
                    return self._run_plan(
                        raw_output=raw_output,
                        plan=fast_plan,
                        user_input=user_input,
                        timings=timings,
                        started_at=started_at,
                    )

            model_started_at = time.perf_counter()
            raw_output = self._chat(messages)
            timings["model_s"] = time.perf_counter() - model_started_at
            timings["plan_source"] = "model"
            if self.verbose:
                print("raw_model_output:")
                print(raw_output)

            parse_started_at = time.perf_counter()
            plan = parse_agent_plan(raw_output)
            timings["parse_s"] = time.perf_counter() - parse_started_at
        except AgentPlanError as exc:
            return {
                "ok": False,
                "kind": "error",
                "speak": "I could not understand the model response safely.",
                "error": str(exc),
                "tool_results": [],
                "raw_model_output": raw_output if "raw_output" in locals() else "",
                "timings": _finish_timings(timings, started_at),
            }
        except Exception as exc:
            return {
                "ok": False,
                "kind": "error",
                "speak": "I could not complete that request.",
                "error": str(exc),
                "tool_results": [],
                "raw_model_output": "",
                "timings": _finish_timings(timings, started_at),
            }

        return self._run_plan(
            raw_output=raw_output,
            plan=plan,
            user_input=user_input,
            timings=timings,
            started_at=started_at,
        )

    def _run_plan(
        self,
        plan: dict[str, Any],
        raw_output: str,
        user_input: str = "",
        timings: dict[str, Any] | None = None,
        started_at: float | None = None,
    ) -> dict[str, Any]:
        timings = timings if timings is not None else {}
        started_at = started_at if started_at is not None else time.perf_counter()
        try:
            validate_started_at = time.perf_counter()
            validated = validate_agent_plan(plan)
            timings["validate_s"] = time.perf_counter() - validate_started_at
        except AgentPlanError as exc:
            return {
                "ok": False,
                "kind": "error",
                "speak": "I could not understand the model response safely.",
                "error": str(exc),
                "tool_results": [],
                "raw_model_output": raw_output,
                "timings": _finish_timings(timings, started_at),
            }

        tool_results: list[dict[str, Any]] = []
        if validated.kind == "tool_request":
            if self.enable_tools:
                tools_started_at = time.perf_counter()
                tool_results = self.tool_executor(validated.tools, user_input=user_input)
                timings["tools_s"] = time.perf_counter() - tools_started_at
                if self.summarize_tool_results:
                    summarize_started_at = time.perf_counter()
                    tool_results = self._summarize_tool_results(tool_results)
                    timings["summarize_s"] = time.perf_counter() - summarize_started_at
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
            "timings": _finish_timings(timings, started_at),
        }

    def _chat(
        self,
        messages: list[dict[str, str]],
        max_tokens: int | None = None,
        json_object: bool | None = None,
    ) -> str:
        if self.mock_llm:
            return MOCK_LLM_RESPONSE
        if self.llama_client is None:
            raise RuntimeError("A llama client is required unless mock_llm is enabled.")
        return self.llama_client.chat(
            messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens if max_tokens is None else max_tokens,
            json_object=self.json_response_format if json_object is None else json_object,
        )

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
                    ],
                    max_tokens=self.summarizer_max_tokens,
                    json_object=False,
                ).strip()
            except Exception:
                summarized.append(updated)
                continue

            if summary:
                updated["spoken_text"] = summary
                updated["summarized"] = True
            summarized.append(updated)

        return summarized


def _finish_timings(timings: dict[str, Any], started_at: float) -> dict[str, Any]:
    finished = dict(timings)
    finished["total_s"] = time.perf_counter() - started_at
    return finished
