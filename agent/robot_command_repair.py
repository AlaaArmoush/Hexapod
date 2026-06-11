from __future__ import annotations

import re
from typing import Any

from bridge.robot_commands import degrees_to_cycles


DEGREES_PATTERN = re.compile(r"\b(\d{1,4})\s*(?:degrees?|deg)\b", re.IGNORECASE)
COUNT_WORDS = {
    "once": 1,
    "twice": 2,
    "thrice": 3,
}


def repair_robot_command_from_text(command: dict[str, Any], user_input: str) -> dict[str, Any]:
    if not isinstance(command, dict):
        return command

    repaired = dict(command)
    cmd = repaired.get("cmd")
    if cmd == "rotate":
        degrees = _extract_degrees(user_input)
        if degrees is not None:
            repaired.pop("degrees", None)
            repaired["cycles"] = max(1, degrees_to_cycles(degrees))

    if cmd == "wave" and "count" in repaired and not _mentions_count(user_input):
        repaired["count"] = 2

    return repaired


def _extract_degrees(user_input: str) -> int | None:
    match = DEGREES_PATTERN.search(user_input)
    if match is None:
        return None
    return int(match.group(1))


def _mentions_count(user_input: str) -> bool:
    lowered = user_input.lower()
    if any(word in lowered for word in COUNT_WORDS):
        return True
    return re.search(r"\b\d+\b", lowered) is not None
