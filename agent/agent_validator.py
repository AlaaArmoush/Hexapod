"""Validation for parsed agent plans."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .agent_errors import (
    AgentPlanValidationError,
    UnknownToolError,
    UnsafeAgentPlanError,
)
from .prompts import ALLOWED_EMOTIONS, ALLOWED_FACES, ALLOWED_TOOLS


ALLOWED_TOP_LEVEL_FIELDS = {"version", "kind", "response", "tools", "safety"}
ALLOWED_KINDS = {"final_response", "tool_request"}
UNSAFE_KEYWORDS = {
    "servo",
    "raw_servo",
    "set_servo",
    "pca_write",
    "i2c_write",
    "serial_write",
    "shell",
    "python",
    "exec",
    "eval",
    "file_write",
    "file_read",
    "raw_pixels",
    "raw_oled",
    "arbitrary_json",
}


@dataclass
class ValidatedAgentPlan:
    version: int
    kind: str
    speak: str
    emotion: str
    face: str
    tools: list[dict[str, Any]]
    actions: list[dict[str, Any]]


def validate_agent_plan(plan: dict) -> ValidatedAgentPlan:
    """Validate a parsed agent plan and return a normalized dataclass."""

    if not isinstance(plan, dict):
        raise AgentPlanValidationError("Agent plan must be a dictionary")

    _reject_unsafe_values(plan)

    unknown_fields = set(plan) - ALLOWED_TOP_LEVEL_FIELDS
    if unknown_fields:
        raise AgentPlanValidationError(
            f"Unknown top-level fields: {', '.join(sorted(unknown_fields))}"
        )

    if plan.get("version") != 1:
        raise AgentPlanValidationError("Agent plan version must be 1")

    kind = plan.get("kind")
    if kind not in ALLOWED_KINDS:
        raise AgentPlanValidationError("Agent plan kind is not allowed")

    response = plan.get("response")
    if not isinstance(response, dict):
        raise AgentPlanValidationError("Agent plan response must be present")

    speak = response.get("speak")
    if not isinstance(speak, str) or not speak.strip():
        raise AgentPlanValidationError("response.speak must be a non-empty string")
    if len(speak) > 240:
        raise AgentPlanValidationError("response.speak must be 240 characters or fewer")
    if "`" in speak:
        raise AgentPlanValidationError("response.speak must not contain code")

    emotion = response.get("emotion")
    if emotion not in ALLOWED_EMOTIONS:
        raise AgentPlanValidationError("response.emotion is not allowed")

    face = response.get("face")
    if face not in ALLOWED_FACES:
        raise AgentPlanValidationError("response.face is not allowed")

    tools = plan.get("tools", [])
    if not isinstance(tools, list):
        raise AgentPlanValidationError("tools must be a list")
    for tool in tools:
        if not isinstance(tool, dict):
            raise AgentPlanValidationError("Each tool must be an object")
        name = tool.get("name")
        if name not in ALLOWED_TOOLS:
            raise UnknownToolError(f"Unknown tool: {name}")

    return ValidatedAgentPlan(
        version=1,
        kind=kind,
        speak=speak,
        emotion=emotion,
        face=face,
        tools=tools,
        actions=[],
    )


def _reject_unsafe_values(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            _reject_unsafe_values(key)
            _reject_unsafe_values(child)
        return

    if isinstance(value, list):
        for child in value:
            _reject_unsafe_values(child)
        return

    if isinstance(value, str):
        lowered = value.lower()
        for keyword in UNSAFE_KEYWORDS:
            if keyword in lowered:
                raise UnsafeAgentPlanError(f"Unsafe keyword found: {keyword}")
