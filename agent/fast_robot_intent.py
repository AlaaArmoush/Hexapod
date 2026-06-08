"""Deterministic fast path for simple robot movement requests."""

from __future__ import annotations

import re
from typing import Any


COUNT_WORDS = {
    "one": 1,
    "once": 1,
    "two": 2,
    "twice": 2,
    "three": 3,
    "thrice": 3,
}
GAIT_SPEED = 0.03
GAIT_DIRECTIONS = {
    "forward_left": ("forward left", "front left"),
    "forward_right": ("forward right", "front right"),
    "backward_left": ("backward left", "back left"),
    "backward_right": ("backward right", "back right"),
    "forward": ("forward",),
    "backward": ("backward", "back", "backwards"),
    "left": ("left", "strafe left"),
    "right": ("right", "strafe right"),
}
COMMAND_VERBS = {"step", "steps", "walk", "walks", "move", "moves", "go", "take"}
QUESTION_PREFIXES = ("how ", "why ", "what ", "when ", "where ", "explain ")
NEGATION_WORDS = {"do not", "don't", "dont", "no ", "not "}


def build_fast_robot_plan(user_input: str) -> dict[str, Any] | None:
    """Return an agent-plan dict for obvious robot commands, or None."""

    text = _normalize(user_input)
    if not text or text.startswith(QUESTION_PREFIXES) or any(word in text for word in NEGATION_WORDS):
        return None

    command = _stop_command(text) or _posture_command(text) or _gait_command(text) or _rotate_command(text)
    if command is None:
        return None

    return {
        "version": 1,
        "kind": "tool_request",
        "response": _response_for_command(command),
        "tools": [{"name": "robot_command", "args": command}],
    }


def _normalize(user_input: str) -> str:
    text = user_input.lower().strip()
    text = re.sub(r"[^a-z0-9_ .-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _stop_command(text: str) -> dict[str, Any] | None:
    if text in {"stop", "halt", "freeze", "hold still"} or text.startswith(("stop ", "halt ")):
        mode = "emergency" if any(word in text for word in ("emergency", "now", "immediately", "e stop", "estop")) else "smooth"
        return {"cmd": "stop", "mode": mode}
    return None


def _posture_command(text: str) -> dict[str, Any] | None:
    if text in {"stand", "stand up", "get up"}:
        return {"cmd": "stand"}
    if text in {"sit", "sit down"}:
        return {"cmd": "sit"}
    if text in {"wave", "wave at me", "wave hello", "wave hi"}:
        return {"cmd": "wave", "leg": "RF", "count": 2}
    if text in {"status", "robot status", "ping"}:
        return {"cmd": "ping" if text == "ping" else "status"}
    return None


def _gait_command(text: str) -> dict[str, Any] | None:
    tokens = set(text.split())
    if not (tokens & COMMAND_VERBS or text in {"back", "back up", "forward", "left", "right"}):
        return None

    direction = _gait_direction(text)
    if direction is None:
        return None

    return {
        "cmd": "gait",
        "dir": direction,
        "speed": GAIT_SPEED,
        "steps": _extract_step_count(text),
    }


def _gait_direction(text: str) -> str | None:
    if "back up" in text:
        return "backward"
    for direction, phrases in GAIT_DIRECTIONS.items():
        if any(_contains_phrase(text, phrase) for phrase in phrases):
            return direction
    return None


def _rotate_command(text: str) -> dict[str, Any] | None:
    if not any(word in text for word in ("turn", "rotate")):
        return None
    if "left" not in text and "right" not in text:
        return None

    command: dict[str, Any] = {"cmd": "rotate", "dir": "right" if "right" in text else "left"}
    degrees = _extract_degrees(text)
    if degrees is not None:
        command["degrees"] = degrees
    else:
        command["cycles"] = _extract_step_count(text)
    return command


def _contains_phrase(text: str, phrase: str) -> bool:
    return re.search(rf"\b{re.escape(phrase)}\b", text) is not None


def _extract_step_count(text: str) -> int:
    digit_match = re.search(r"\b([1-3])\b", text)
    if digit_match is not None:
        return int(digit_match.group(1))
    for word, count in COUNT_WORDS.items():
        if _contains_phrase(text, word):
            return count
    return 1


def _extract_degrees(text: str) -> int | None:
    match = re.search(r"\b(\d{1,3})\s*(?:degrees?|deg)\b", text)
    if match is None:
        return None
    return int(match.group(1))


def _response_for_command(command: dict[str, Any]) -> dict[str, str]:
    cmd = command["cmd"]
    if cmd == "gait":
        phrase = "Stepping back." if command["dir"] == "backward" else f"Stepping {command['dir'].replace('_', ' ')}."
        return {"speak": phrase, "emotion": "neutral", "face": "walking"}
    if cmd == "rotate":
        return {"speak": f"Turning {command['dir']}.", "emotion": "neutral", "face": "walking"}
    if cmd == "wave":
        return {"speak": "Waving!", "emotion": "happy", "face": "waving"}
    if cmd == "stop":
        return {"speak": "Stopping.", "emotion": "neutral", "face": "system"}
    if cmd == "stand":
        return {"speak": "Standing up.", "emotion": "neutral", "face": "system"}
    if cmd == "sit":
        return {"speak": "Sitting down.", "emotion": "neutral", "face": "system"}
    return {"speak": "Checking robot status.", "emotion": "neutral", "face": "system"}
