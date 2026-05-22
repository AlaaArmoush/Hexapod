from __future__ import annotations

from .bridge_errors import AmbiguousCommandError, InvalidParameterError


FORBIDDEN_FIELDS = {"servo", "angle", "pwm", "board", "channel", "pixel", "bitmap", "raw"}
GAIT_DIRECTIONS = {
    "forward",
    "backward",
    "left",
    "right",
    "forward_left",
    "forward_right",
    "backward_left",
    "backward_right",
}
ROTATE_DIRECTIONS = {"left", "right"}
WAVE_LEGS = {"LF", "RF"}
WAVE_COUNT_RANGE = (1, 6)
GAIT_SPEED_RANGE = (0.03, 1.0)
BODY_OFFSET_RANGE = (-50.0, 50.0)
GESTURE_INTENSITY_RANGE = (0.0, 1.0)
DEGREES_PER_CYCLE = 30
LEAN_DIRECTIONS = {"left", "right", "forward", "backward"}
LOOK_DIRECTIONS = {"left", "right", "up", "down", "center"}
IDLE_STYLES = {"breathing", "sway"}


def _ensure_number(value: object, name: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidParameterError(f"{name} must be a number, got {value!r}")
    return value


def _ensure_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidParameterError(f"{name} must be an int, got {value!r}")
    return value


def _ensure_string(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise InvalidParameterError(f"{name} must be a string, got {value!r}")
    return value


def _ensure_range(value: object, name: str, lower: float, upper: float) -> int | float:
    number = _ensure_number(value, name)
    if number < lower or number > upper:
        raise InvalidParameterError(f"{name} must be between {lower} and {upper}, got {value!r}")
    return number


def _ensure_positive(value: object, name: str) -> int | float:
    number = _ensure_number(value, name)
    if number <= 0:
        raise InvalidParameterError(f"{name} must be > 0, got {value!r}")
    return number


def _ensure_non_negative(value: object, name: str) -> int | float:
    number = _ensure_number(value, name)
    if number < 0:
        raise InvalidParameterError(f"{name} must be >= 0, got {value!r}")
    return number


def _ensure_no_forbidden_fields(command: dict) -> dict:
    forbidden = FORBIDDEN_FIELDS.intersection(command)
    if forbidden:
        raise InvalidParameterError(f"command contains forbidden raw-control fields: {sorted(forbidden)}")
    return command


def build_ping() -> dict:
    return {"cmd": "ping"}


def build_status() -> dict:
    return {"cmd": "status"}


def build_stand() -> dict:
    return {"cmd": "stand"}


def build_sit() -> dict:
    return {"cmd": "sit"}


def build_stop(mode: str = "smooth") -> dict:
    if mode not in ("smooth", "emergency"):
        raise InvalidParameterError(f"stop mode must be 'smooth' or 'emergency', got {mode!r}")
    return {"cmd": "stop", "mode": mode}


def build_gait(
    dir: str = "forward",
    speed: float = 0.25,
    duration_ms: int | None = None,
    steps: int | None = None,
    distance_cm: float | None = None,
    step_len: float | None = None,
    step_ht: float | None = None,
) -> dict:
    dir = _ensure_string(dir, "dir")
    if dir not in GAIT_DIRECTIONS:
        raise InvalidParameterError(f"gait dir must be one of {sorted(GAIT_DIRECTIONS)}, got {dir!r}")
    _ensure_range(speed, "speed", *GAIT_SPEED_RANGE)

    bounds = {
        "duration_ms": duration_ms,
        "steps": steps,
        "distance_cm": distance_cm,
    }
    provided_bounds = [name for name, value in bounds.items() if value is not None]
    if len(provided_bounds) > 1:
        raise AmbiguousCommandError(f"gait bounds are mutually exclusive: {provided_bounds}")

    command = {"cmd": "gait", "dir": dir, "speed": speed}
    if duration_ms is not None:
        command["duration_ms"] = _ensure_int(duration_ms, "duration_ms")
        _ensure_positive(duration_ms, "duration_ms")
    if steps is not None:
        command["steps"] = _ensure_int(steps, "steps")
        _ensure_positive(steps, "steps")
    if distance_cm is not None:
        command["distance_cm"] = _ensure_positive(distance_cm, "distance_cm")
    if step_len is not None:
        command["step_len"] = _ensure_non_negative(step_len, "step_len")
    if step_ht is not None:
        command["step_ht"] = _ensure_non_negative(step_ht, "step_ht")
    return _ensure_no_forbidden_fields(command)


def build_rotate(
    dir: str = "left",
    cycles: int | None = None,
    degrees: int | None = None,
    continuous: bool = False,
) -> dict:
    dir = _ensure_string(dir, "dir")
    if dir not in ROTATE_DIRECTIONS:
        raise InvalidParameterError(f"rotate dir must be one of {sorted(ROTATE_DIRECTIONS)}, got {dir!r}")
    if not isinstance(continuous, bool):
        raise InvalidParameterError(f"continuous must be a bool, got {continuous!r}")

    provided_bounds = [
        name
        for name, active in (
            ("cycles", cycles is not None),
            ("degrees", degrees is not None),
            ("continuous", continuous),
        )
        if active
    ]
    if len(provided_bounds) > 1:
        raise AmbiguousCommandError(f"rotate bounds are mutually exclusive: {provided_bounds}")

    command = {"cmd": "rotate", "dir": dir}
    if cycles is not None:
        command["cycles"] = _ensure_int(cycles, "cycles")
        _ensure_positive(cycles, "cycles")
    if degrees is not None:
        command["degrees"] = _ensure_int(degrees, "degrees")
        _ensure_positive(degrees, "degrees")
    if continuous:
        command["continuous"] = True
    return _ensure_no_forbidden_fields(command)


def degrees_to_cycles(degrees: int) -> int:
    _ensure_int(degrees, "degrees")
    return round(degrees / DEGREES_PER_CYCLE)


def build_wave(leg: str = "RF", count: int = 2) -> dict:
    leg = _ensure_string(leg, "leg").upper()
    if leg not in WAVE_LEGS:
        raise InvalidParameterError(f"wave leg must be one of {sorted(WAVE_LEGS)}, got {leg!r}")
    _ensure_int(count, "count")
    low, high = WAVE_COUNT_RANGE
    if count < low or count > high:
        raise InvalidParameterError(f"count must be between {low} and {high}, got {count!r}")
    return {"cmd": "wave", "leg": leg, "count": count}


def build_gesture(name: str = "idle", intensity: float = 0.5) -> dict:
    name = _ensure_string(name, "name")
    _ensure_range(intensity, "intensity", *GESTURE_INTENSITY_RANGE)
    return {"cmd": "gesture", "name": name, "intensity": intensity}


def build_body(x: float = 0.0, y: float = 0.0, z: float = 0.0) -> dict:
    low, high = BODY_OFFSET_RANGE
    return {
        "cmd": "body",
        "x": _ensure_range(x, "x", low, high),
        "y": _ensure_range(y, "y", low, high),
        "z": _ensure_range(z, "z", low, high),
    }


def build_face(name: str = "idle", duration_ms: int | None = None, persistent: bool = False) -> dict:
    name = _ensure_string(name, "name")
    if not isinstance(persistent, bool):
        raise InvalidParameterError(f"persistent must be a bool, got {persistent!r}")
    command = {"cmd": "face", "name": name}
    if duration_ms is not None:
        command["duration_ms"] = _ensure_int(duration_ms, "duration_ms")
        _ensure_positive(duration_ms, "duration_ms")
    if persistent:
        command["persistent"] = True
    return _ensure_no_forbidden_fields(command)


def build_blink() -> dict:
    return {"cmd": "blink"}


def build_idle(style: str = "breathing") -> dict:
    if style not in IDLE_STYLES:
        raise InvalidParameterError(f"idle style must be 'breathing' or 'sway', got {style!r}")
    return {"cmd": "idle", "style": style}


def build_lean(dir: str = "left", amount_mm: float = 20.0, duration_ms: int = 400) -> dict:
    dir = _ensure_string(dir, "dir")
    if dir not in LEAN_DIRECTIONS:
        raise InvalidParameterError(f"lean dir must be one of {sorted(LEAN_DIRECTIONS)}, got {dir!r}")
    _ensure_positive(amount_mm, "amount_mm")
    _ensure_int(duration_ms, "duration_ms")
    _ensure_positive(duration_ms, "duration_ms")
    return {"cmd": "lean", "dir": dir, "amount_mm": amount_mm, "duration_ms": duration_ms}


def build_look(dir: str = "center", duration_ms: int | None = None, persistent: bool = False) -> dict:
    dir = _ensure_string(dir, "dir")
    if dir not in LOOK_DIRECTIONS:
        raise InvalidParameterError(f"look dir must be one of {sorted(LOOK_DIRECTIONS)}, got {dir!r}")
    if not isinstance(persistent, bool):
        raise InvalidParameterError(f"persistent must be a bool, got {persistent!r}")
    command = {"cmd": "look", "dir": dir}
    if duration_ms is not None:
        command["duration_ms"] = _ensure_int(duration_ms, "duration_ms")
        _ensure_positive(duration_ms, "duration_ms")
    if persistent:
        command["persistent"] = True
    return _ensure_no_forbidden_fields(command)


def build_nod(count: int = 2) -> dict:
    _ensure_int(count, "count")
    _ensure_positive(count, "count")
    return {"cmd": "nod", "count": count}


def build_shake(count: int = 2) -> dict:
    _ensure_int(count, "count")
    _ensure_positive(count, "count")
    return {"cmd": "shake", "count": count}
