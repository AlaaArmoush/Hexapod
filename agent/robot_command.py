"""Validate robot_command tool args using the existing bridge protocol."""

from __future__ import annotations

from typing import Any, Callable

from bridge import BridgeError
from bridge.robot_commands import (
    build_blink,
    build_body,
    build_face,
    build_gait,
    build_gesture,
    build_idle,
    build_lean,
    build_look,
    build_nod,
    build_ping,
    build_rotate,
    build_shake,
    build_sit,
    build_stand,
    build_status,
    build_stop,
    build_wave,
    degrees_to_cycles,
)

from .agent_errors import UnknownActionError, UnsafeAgentPlanError


DEFAULT_LLM_GAIT_SPEED = 0.03

UNSAFE_ROBOT_KEYWORDS = {
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
}


def compile_robot_command(command: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize a Gemma-planned robot command."""

    if not isinstance(command, dict):
        raise UnknownActionError("Robot command must be a JSON object")

    _reject_unsafe(command)

    cmd = command.get("cmd")
    if not isinstance(cmd, str):
        raise UnknownActionError("Robot command must include a string cmd")
    if cmd == "unknown":
        raise UnknownActionError("Model could not map the request to a robot command")

    builder = _COMMAND_BUILDERS.get(cmd)
    if builder is None:
        raise UnknownActionError(f"Unknown robot command: {cmd}")

    args = {key: value for key, value in command.items() if key != "cmd"}
    try:
        return builder(args)
    except BridgeError:
        raise


def _reject_unsafe(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            _reject_unsafe(key)
            _reject_unsafe(child)
        return

    if isinstance(value, list):
        for child in value:
            _reject_unsafe(child)
        return

    if isinstance(value, str):
        lowered = value.lower()
        for keyword in UNSAFE_ROBOT_KEYWORDS:
            if keyword in lowered:
                raise UnsafeAgentPlanError(f"Unsafe robot command keyword found: {keyword}")


def _no_args(builder: Callable[[], dict[str, Any]]) -> Callable[[dict[str, Any]], dict[str, Any]]:
    def call(args: dict[str, Any]) -> dict[str, Any]:
        if args:
            raise UnknownActionError(f"Command does not accept args: {sorted(args)}")
        return builder()

    return call


def _build_stop(args: dict[str, Any]) -> dict[str, Any]:
    _ensure_allowed_args(args, {"mode"})
    return build_stop(mode=args.get("mode", "smooth"))


def _build_gait(args: dict[str, Any]) -> dict[str, Any]:
    _ensure_allowed_args(
        args,
        {"dir", "speed", "duration_ms", "steps", "distance_cm", "step_len", "step_ht"},
    )
    return build_gait(
        dir=args.get("dir", "forward"),
        speed=args.get("speed", DEFAULT_LLM_GAIT_SPEED),
        duration_ms=args.get("duration_ms"),
        steps=args.get("steps"),
        distance_cm=args.get("distance_cm"),
        step_len=args.get("step_len"),
        step_ht=args.get("step_ht"),
    )


def _build_rotate(args: dict[str, Any]) -> dict[str, Any]:
    _ensure_allowed_args(args, {"dir", "cycles", "degrees", "continuous"})
    if args.get("continuous") is True:
        raise UnknownActionError("Continuous rotation is not allowed for robot_command")
    if args.get("degrees") is not None and args.get("cycles") is None:
        args = dict(args)
        args["cycles"] = max(1, degrees_to_cycles(args["degrees"]))
        args.pop("degrees")
    return build_rotate(
        dir=args.get("dir", "left"),
        cycles=args.get("cycles"),
        degrees=args.get("degrees"),
        continuous=args.get("continuous", False),
    )


def _build_wave(args: dict[str, Any]) -> dict[str, Any]:
    _ensure_allowed_args(args, {"leg", "count"})
    return build_wave(leg=args.get("leg", "RF"), count=args.get("count", 2))


def _build_gesture(args: dict[str, Any]) -> dict[str, Any]:
    _ensure_allowed_args(args, {"name", "intensity"})
    return build_gesture(name=args.get("name", "idle"), intensity=args.get("intensity", 0.5))


def _build_body(args: dict[str, Any]) -> dict[str, Any]:
    _ensure_allowed_args(args, {"x", "y", "z"})
    return build_body(x=args.get("x", 0.0), y=args.get("y", 0.0), z=args.get("z", 0.0))


def _build_face(args: dict[str, Any]) -> dict[str, Any]:
    _ensure_allowed_args(args, {"name", "duration_ms", "persistent"})
    return build_face(
        name=args.get("name", "idle"),
        duration_ms=args.get("duration_ms"),
        persistent=args.get("persistent", False),
    )


def _build_idle(args: dict[str, Any]) -> dict[str, Any]:
    _ensure_allowed_args(args, {"style"})
    return build_idle(style=args.get("style", "breathing"))


def _build_lean(args: dict[str, Any]) -> dict[str, Any]:
    _ensure_allowed_args(args, {"dir", "amount_mm", "duration_ms"})
    return build_lean(
        dir=args.get("dir", "left"),
        amount_mm=args.get("amount_mm", 20.0),
        duration_ms=args.get("duration_ms", 400),
    )


def _build_look(args: dict[str, Any]) -> dict[str, Any]:
    _ensure_allowed_args(args, {"dir", "duration_ms", "persistent"})
    return build_look(
        dir=args.get("dir", "center"),
        duration_ms=args.get("duration_ms"),
        persistent=args.get("persistent", False),
    )


def _build_nod(args: dict[str, Any]) -> dict[str, Any]:
    _ensure_allowed_args(args, {"count"})
    return build_nod(count=args.get("count", 2))


def _build_shake(args: dict[str, Any]) -> dict[str, Any]:
    _ensure_allowed_args(args, {"count"})
    return build_shake(count=args.get("count", 2))


def _ensure_allowed_args(args: dict[str, Any], allowed: set[str]) -> None:
    unexpected = set(args) - allowed
    if unexpected:
        raise UnknownActionError(f"Unexpected robot command args: {sorted(unexpected)}")


_COMMAND_BUILDERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "status": _no_args(build_status),
    "ping": _no_args(build_ping),
    "stand": _no_args(build_stand),
    "sit": _no_args(build_sit),
    "blink": _no_args(build_blink),
    "stop": _build_stop,
    "gait": _build_gait,
    "rotate": _build_rotate,
    "wave": _build_wave,
    "gesture": _build_gesture,
    "body": _build_body,
    "face": _build_face,
    "idle": _build_idle,
    "lean": _build_lean,
    "look": _build_look,
    "nod": _build_nod,
    "shake": _build_shake,
}
