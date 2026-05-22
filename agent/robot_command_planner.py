"""Plan and validate robot serial commands using the existing bridge protocol."""

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
)

from .agent_errors import UnknownActionError, UnsafeAgentPlanError
from .agent_plan import parse_agent_plan


ROBOT_COMMAND_PROMPT = """
You convert user text into exactly one compact JSON object for a hexapod robot.
Return JSON only. No markdown. No explanation. No extra text.

Allowed commands:
{"cmd":"ping"}
{"cmd":"status"}
{"cmd":"stand"}
{"cmd":"sit"}
{"cmd":"stop"}
{"cmd":"stop","mode":"emergency"}
{"cmd":"wave","leg":"RF","count":2}
{"cmd":"gait","dir":"forward","speed":0.05}
{"cmd":"rotate","dir":"right","cycles":3}
{"cmd":"gesture","name":"happy","intensity":0.7}
{"cmd":"body","x":0,"y":0,"z":0}
{"cmd":"face","name":"happy","duration_ms":1000}
{"cmd":"blink"}
{"cmd":"idle","style":"breathing"}
{"cmd":"lean","dir":"left","amount_mm":20,"duration_ms":400}
{"cmd":"look","dir":"center"}
{"cmd":"nod","count":2}
{"cmd":"shake","count":2}

Rules:
- Use only the keys shown for each command. Do not add extra keys.
- gait dir: forward, backward, left, right, forward_left, forward_right, backward_left, backward_right.
- gait speed must be 0.05 to 1.0.
- gait may include only one of: duration_ms, steps, distance_cm.
- rotate dir: left or right.
- rotate may include only one of: cycles, degrees, continuous.
- 1 rotate cycle = 30 degrees.
- turn around = rotate 180 degrees = 6 cycles.
- slow gait speed = 0.05, normal = 0.25, fast = 0.5.
- wave leg must be LF or RF.
- default wave count is 2.
- gesture intensity must be 0.0 to 1.0.
- body x/y/z must be -50 to 50.
- idle style must be breathing or sway.
- lean dir must be left, right, forward, or backward.
- look dir must be left, right, up, down, or center.
- If the user is just greeting, wave.
- If the request is not a robot command, return {"cmd":"unknown"}.
- Never output raw servo fields, low-level writes, shell commands, Python code, or arbitrary JSON.
""".strip()


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
    "raw",
}


class RobotCommandPlanner:
    """Ask a local model for existing serial-protocol command JSON."""

    def __init__(
        self,
        llama_client: Any,
        temperature: float = 0,
        max_tokens: int = 80,
        prompt: str = ROBOT_COMMAND_PROMPT,
    ):
        self.llama_client = llama_client
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.prompt = prompt

    def plan_command(self, user_input: str) -> dict[str, Any]:
        raw_output = self.llama_client.chat(
            [
                {"role": "system", "content": self.prompt},
                {"role": "user", "content": user_input},
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            json_object=True,
        )
        command = parse_agent_plan(raw_output)
        return compile_robot_command(command)


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
        speed=args.get("speed", 0.25),
        duration_ms=args.get("duration_ms"),
        steps=args.get("steps"),
        distance_cm=args.get("distance_cm"),
        step_len=args.get("step_len"),
        step_ht=args.get("step_ht"),
    )


def _build_rotate(args: dict[str, Any]) -> dict[str, Any]:
    _ensure_allowed_args(args, {"dir", "cycles", "degrees", "continuous"})
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
