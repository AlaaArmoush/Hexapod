from __future__ import annotations

import re
from typing import Any


COUNT_WORDS = {
    "one": 1, "once": 1,
    "two": 2, "twice": 2,
    "three": 3, "thrice": 3,
}
GAIT_SPEED = 0.06
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

# Maps colloquial emotion/expression words to valid firmware face names.
FACE_NAME_MAP: dict[str, str] = {
    "happy": "happy",
    "glad": "happy",
    "joyful": "happy",
    "sad": "sad",
    "unhappy": "sad",
    "confused": "confused",
    "curious": "curious",
    "surprised": "surprised",
    "shocked": "surprised",
    "scared": "scared",
    "afraid": "scared",
    "neutral": "neutral",
    "thinking": "thinking",
    "love": "love",
    "sleepy": "sleepy",
    "tired": "sleepy",
    "alert": "alert",
    "dizzy": "dizzy",
    "excited": "starstruck",
    "starstruck": "starstruck",
    "success": "success",
    "error": "error",
}

# Named gestures the firmware's gesture controller supports.
GESTURE_NAME_MAP: dict[str, str] = {
    "happy": "happy",
    "excited": "excited",
    "sad": "sad",
    "curious": "curious",
    "scared": "scared",
    "confused": "confused",
}

# Info tool fast-paths: (trigger phrases, tool_name, speak, emotion, face).
# Triggers use simple substring matching after normalization.
_INFO_TOOLS: list[tuple[tuple[str, ...], str, str, str, str]] = [
    (
        ("what time", "what s the time", "tell me the time", "current time", "check the time"),
        "get_time", "Checking the time.", "thinking", "clock",
    ),
    (
        ("what day", "what date", "what s the date", "today s date", "tell me the date", "current date"),
        "get_date", "Checking the date.", "thinking", "calendar",
    ),
    (
        ("battery", "power level", "how much charge", "how much power", "check power"),
        "battery_status", "Checking battery.", "thinking", "battery",
    ),
    (
        ("system status", "self check", "self-check", "run diagnostics", "diagnostics"),
        "system_status", "Running system check.", "thinking", "system",
    ),
    (
        ("camera status", "is the camera", "camera working", "check the camera"),
        "camera_status", "Checking camera.", "thinking", "camera",
    ),
    (
        ("mic status", "microphone status", "is the mic", "mic working", "check the mic"),
        "mic_status", "Checking microphone.", "thinking", "microphone",
    ),
    (
        ("network status", "wifi status", "check wifi", "check network", "am i connected"),
        "network_status", "Checking network.", "thinking", "wifi",
    ),
    (
        ("where did that come from", "which direction was", "voice direction", "where was that voice", "which way was"),
        "voice_direction_estimate", "Estimating direction.", "thinking", "scan",
    ),
    (
        ("how far", "depth check", "check depth", "how close", "measure distance"),
        "depth_probe", "Probing depth.", "thinking", "camera",
    ),
    (
        ("what do you see", "look around", "describe what you see", "scan the room", "what s around", "observe the scene"),
        "observe_scene", "Looking around.", "thinking", "camera",
    ),
    (
        ("do you see anyone", "is anyone there", "is someone there", "detect a person", "find a person"),
        "detect_person", "Looking for a person.", "thinking", "camera",
    ),
    (
        ("describe the scene", "describe what you see", "describe what s around", "describe around you", "describe what s in front"),
        "describe_scene", "Describing the scene.", "thinking", "camera",
    ),
    (
        ("take a photo", "take a picture", "snap a photo", "snap a picture", "capture a photo", "capture a picture", "take photo", "take picture"),
        "capture_image", "Taking a photo.", "thinking", "camera",
    ),
]


def build_fast_robot_plan(user_input: str) -> dict[str, Any] | None:
    text = _normalize(user_input)
    if not text:
        return None

    has_negation = any(word in text for word in NEGATION_WORDS)
    if has_negation:
        return None

    is_question = text.startswith(QUESTION_PREFIXES)

    if not is_question:
        command = (
            _stop_command(text)
            or _posture_command(text)
            or _gait_command(text)
            or _rotate_command(text)
            or _gesture_command(text)
            or _look_command(text)
            or _lean_command(text)
            or _idle_command(text)
            or _face_command(text)
        )
        if command is not None:
            return {
                "version": 1,
                "kind": "tool_request",
                "response": _response_for_command(command),
                "tools": [{"name": "robot_command", "args": command}],
            }

    return _info_tool_plan(text) or _timer_plan(text)


def _normalize(user_input: str) -> str:
    text = user_input.lower().strip()
    text = re.sub(r"[^a-z0-9_ .-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"[.,!?]+$", "", text).strip()
    return text


# ---------------------------------------------------------------------------
# Robot command matchers
# ---------------------------------------------------------------------------


def _stop_command(text: str) -> dict[str, Any] | None:
    if text in {"stop", "halt", "freeze", "hold still"} or text.startswith(("stop ", "halt ")):
        mode = "emergency" if any(word in text for word in ("emergency", "now", "immediately", "e stop", "estop")) else "smooth"
        return {"cmd": "stop", "mode": mode}
    return None


def _posture_command(text: str) -> dict[str, Any] | None:
    if text in {"stand", "stand up", "get up"}:
        return {"cmd": "stand"}
    if text in {"sit", "sit down", "rest"}:
        return {"cmd": "sit"}
    if _contains_phrase(text, "wave"):
        leg = "LF" if "left" in text.split() else "RF"
        count = _extract_step_count(text)
        return {"cmd": "wave", "leg": leg, "count": max(1, count)}
    if text in {"status", "robot status"}:
        return {"cmd": "status"}
    if text == "ping":
        return {"cmd": "ping"}
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


def _gesture_command(text: str) -> dict[str, Any] | None:
    tokens = set(text.split())

    if "blink" in tokens and "blinking" not in text:
        return {"cmd": "blink"}

    if _contains_phrase(text, "nod"):
        return {"cmd": "nod", "count": _extract_step_count(text)}

    if _contains_phrase(text, "shake") and not _contains_phrase(text, "milkshake"):
        return {"cmd": "shake", "count": _extract_step_count(text)}

    gesture_intent = any(_contains_phrase(text, t) for t in ("gesture", "act", "perform", "do a", "do the"))
    if gesture_intent:
        for keyword, name in GESTURE_NAME_MAP.items():
            if _contains_phrase(text, keyword):
                return {"cmd": "gesture", "name": name, "intensity": 0.7}

    return None


def _look_command(text: str) -> dict[str, Any] | None:
    # Camera pan (horizontal servo)
    for phrase, pos in (
        ("look front left", "front_left"),
        ("pan front left", "front_left"),
        ("look front right", "front_right"),
        ("pan front right", "front_right"),
        ("look left", "left"),
        ("pan left", "left"),
        ("camera left", "left"),
        ("face left", "left"),
        ("look right", "right"),
        ("pan right", "right"),
        ("camera right", "right"),
        ("face right", "right"),
    ):
        if _contains_phrase(text, phrase):
            return {"cmd": "camera_pan", "pos": pos}

    for phrase in ("center camera", "reset camera", "look ahead", "look straight", "look forward", "look center", "pan center"):
        if _contains_phrase(text, phrase):
            return {"cmd": "camera_center"}

    # Body look / head tilt (vertical and explicit tilt)
    for phrase, dir_name in (
        ("look up", "up"),
        ("tilt up", "up"),
        ("look down", "down"),
        ("tilt down", "down"),
        ("tilt left", "left"),
        ("tilt right", "right"),
        ("center head", "center"),
        ("reset head", "center"),
    ):
        if _contains_phrase(text, phrase):
            return {"cmd": "look", "dir": dir_name}

    return None


def _lean_command(text: str) -> dict[str, Any] | None:
    if not _contains_phrase(text, "lean"):
        return None
    for dir_name, phrases in (
        ("left", ("lean left",)),
        ("right", ("lean right",)),
        ("forward", ("lean forward",)),
        ("backward", ("lean backward", "lean back")),
    ):
        if any(_contains_phrase(text, p) for p in phrases):
            return {"cmd": "lean", "dir": dir_name, "amount_mm": 20.0, "duration_ms": 400}
    return None


def _idle_command(text: str) -> dict[str, Any] | None:
    tokens = set(text.split())
    if "sway" in tokens or "swaying" in tokens:
        return {"cmd": "idle", "style": "sway"}
    if "breathing" in tokens or "breathe" in tokens:
        return {"cmd": "idle", "style": "breathing"}
    if text in {"idle", "go idle", "start idle", "idle mode", "be idle"}:
        return {"cmd": "idle", "style": "breathing"}
    return None


def _face_command(text: str) -> dict[str, Any] | None:
    for keyword, face_name in FACE_NAME_MAP.items():
        if _contains_phrase(text, keyword + " face"):
            return {"cmd": "face", "name": face_name}
        for verb in ("show", "make", "display", "appear", "look"):
            if _contains_phrase(text, f"{verb} {keyword}"):
                return {"cmd": "face", "name": face_name}
    return None


def _info_tool_plan(text: str) -> dict[str, Any] | None:
    for triggers, tool_name, speak, emotion, face in _INFO_TOOLS:
        if any(t in text for t in triggers):
            return {
                "version": 1,
                "kind": "tool_request",
                "response": {"speak": speak, "emotion": emotion, "face": face},
                "tools": [{"name": tool_name, "args": {}}],
            }
    return None


def _timer_plan(text: str) -> dict[str, Any] | None:
    if not any(t in text for t in ("timer", "set a timer", "start a timer")):
        return None
    seconds = _extract_duration_seconds(text)
    if seconds is None:
        return None
    label = _human_duration(seconds)
    return {
        "version": 1,
        "kind": "tool_request",
        "response": {"speak": f"Setting a timer for {label}.", "emotion": "neutral", "face": "timer"},
        "tools": [{"name": "set_timer", "args": {"duration_seconds": seconds}}],
    }


def _extract_duration_seconds(text: str) -> int | None:
    match = re.search(r"\b(\d+)\s*(hour|hr|minute|min|second|sec)s?\b", text)
    if match is None:
        return None
    amount = int(match.group(1))
    unit = match.group(2)
    if unit in ("hour", "hr"):
        return amount * 3600
    if unit in ("minute", "min"):
        return amount * 60
    return amount  # seconds


def _human_duration(seconds: int) -> str:
    if seconds >= 3600 and seconds % 3600 == 0:
        n = seconds // 3600
        return f"{n} hour{'s' if n != 1 else ''}"
    if seconds >= 60 and seconds % 60 == 0:
        n = seconds // 60
        return f"{n} minute{'s' if n != 1 else ''}"
    return f"{seconds} second{'s' if seconds != 1 else ''}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _contains_phrase(text: str, phrase: str) -> bool:
    return re.search(rf"\b{re.escape(phrase)}\b", text) is not None


def _extract_step_count(text: str) -> int:
    digit_match = re.search(r"\b([1-9][0-9]?)\b", text)
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
        return {"speak": f"Turning {command['dir']}.", "emotion": "neutral", "face": "rotating"}
    if cmd == "wave":
        return {"speak": "Waving!", "emotion": "happy", "face": "waving"}
    if cmd == "stop":
        return {"speak": "Stopping.", "emotion": "neutral", "face": "system"}
    if cmd == "stand":
        return {"speak": "Standing up.", "emotion": "neutral", "face": "system"}
    if cmd == "sit":
        return {"speak": "Sitting down.", "emotion": "neutral", "face": "system"}
    if cmd == "blink":
        return {"speak": "Blinking.", "emotion": "neutral", "face": "blinking"}
    if cmd == "nod":
        return {"speak": "Nodding.", "emotion": "neutral", "face": "neutral"}
    if cmd == "shake":
        return {"speak": "Shaking.", "emotion": "neutral", "face": "neutral"}
    if cmd == "gesture":
        name = command.get("name", "idle")
        emotion = name if name in {"happy", "excited", "sad", "curious", "scared", "confused"} else "neutral"
        face = name if name in {"happy", "sad", "curious", "confused"} else "neutral"
        return {"speak": f"Expressing {name}.", "emotion": emotion, "face": face}
    if cmd == "camera_pan":
        pos = command.get("pos", "center").replace("_", " ")
        return {"speak": f"Looking {pos}.", "emotion": "neutral", "face": "camera"}
    if cmd == "camera_center":
        return {"speak": "Centering view.", "emotion": "neutral", "face": "camera"}
    if cmd == "look":
        return {"speak": f"Tilting {command.get('dir', 'center')}.", "emotion": "neutral", "face": "neutral"}
    if cmd == "lean":
        return {"speak": f"Leaning {command.get('dir', 'left')}.", "emotion": "neutral", "face": "neutral"}
    if cmd == "idle":
        style = command.get("style", "breathing")
        speak = "Swaying." if style == "sway" else "Going idle."
        return {"speak": speak, "emotion": "calm", "face": "idle"}
    if cmd == "face":
        name = command.get("name", "neutral")
        return {"speak": f"Showing {name}.", "emotion": "neutral", "face": name}
    return {"speak": "Checking robot status.", "emotion": "neutral", "face": "system"}
