from __future__ import annotations

import json

from .agent_errors import AgentPlanParseError


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```") or not stripped.endswith("```"):
        return stripped

    lines = stripped.splitlines()
    if len(lines) < 2:
        return stripped
    if not lines[0].startswith("```") or lines[-1].strip() != "```":
        return stripped

    return "\n".join(lines[1:-1]).strip()


def parse_agent_plan(text: str) -> dict:
    candidate = _strip_code_fences(text)
    decoder = json.JSONDecoder()

    objects = []
    index = 0
    while index < len(candidate):
        start = candidate.find("{", index)
        if start == -1:
            break
        try:
            parsed, end = decoder.raw_decode(candidate[start:])
        except json.JSONDecodeError as exc:
            raise AgentPlanParseError("Model output contains malformed JSON") from exc
        objects.append(parsed)
        index = start + end

    if not objects:
        raise AgentPlanParseError("Model output did not contain a JSON object")
    if len(objects) > 1:
        raise AgentPlanParseError("Model output contained more than one JSON object")
    if not isinstance(objects[0], dict):
        raise AgentPlanParseError("Model output JSON must be an object")

    return objects[0]

