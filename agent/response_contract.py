"""Shared response contract for agent output fields."""

from __future__ import annotations

from tools import list_all


_REGISTERED_TOOLS = list_all()

ALLOWED_TOOLS = {tool.name for tool in _REGISTERED_TOOLS} | {"robot_command"}

ALLOWED_EMOTIONS = {
    "neutral",
    "happy",
    "thinking",
    "concerned",
    "excited",
    "calm",
}

# Keep this mirrored with include/display_controller.h and displayParseFaceName().
FIRMWARE_COMPATIBLE_FACES = {
    "idle",
    "neutral",
    "happy",
    "curious",
    "scared",
    "sleepy",
    "listening",
    "walking",
    "rotating",
    "waving",
    "error",
    "blinking",
    "thinking",
    "love",
    "surprised",
    "starstruck",
    "dizzy",
    "confused",
    "sad",
    "sleep",
    "loading",
    "alert",
    "low_battery",
    "boop",
    "scan",
    "clock",
    "calendar",
    "search",
    "camera",
    "memory",
    "timer",
    "reminder",
    "battery",
    "system",
    "wifi",
    "microphone",
    "speaking",
    "success",
}

BASE_RESPONSE_FACES = {
    "idle",
    "neutral",
    "happy",
    "thinking",
    "clock",
    "calendar",
    "search",
    "memory",
    "timer",
    "system",
    "wifi",
    "battery",
}

TOOL_RECOMMENDED_FACES = {tool.recommended_display_face for tool in _REGISTERED_TOOLS}
UNSUPPORTED_TOOL_RECOMMENDED_FACES = TOOL_RECOMMENDED_FACES - FIRMWARE_COMPATIBLE_FACES

if UNSUPPORTED_TOOL_RECOMMENDED_FACES:
    raise ValueError(
        "Tool registry recommends unsupported display faces: "
        + ", ".join(sorted(UNSUPPORTED_TOOL_RECOMMENDED_FACES))
    )

ALLOWED_FACES = BASE_RESPONSE_FACES | TOOL_RECOMMENDED_FACES
