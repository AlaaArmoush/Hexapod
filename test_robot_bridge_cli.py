#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any, Callable

from bridge import BridgeError, FirmwareError, SerialRobotBridge, TimeoutError
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


CommandBuilder = Callable[[argparse.Namespace], dict[str, Any]]


def _json_dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, separators=(",", ":"))


def _print_received(response: dict[str, Any], verbose: bool) -> None:
    if response["json"] is not None or verbose:
        print(f"<<< {response['raw']}")


def _read_until_ready(bridge: SerialRobotBridge, timeout: float, verbose: bool) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = bridge.read_json_line()
        if response is None:
            continue
        _print_received(response, verbose)
        if response["event"] == "ready":
            return response
    raise TimeoutError(f"timed out waiting for ready event after {timeout:.2f}s")


def _read_until_response(
    bridge: SerialRobotBridge,
    command: dict[str, Any],
    timeout: float,
    verbose: bool,
) -> dict[str, Any]:
    expected_cmd = str(command["cmd"])
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = bridge.read_json_line()
        if response is None:
            continue
        _print_received(response, verbose)

        if response["json"] is None:
            continue
        if response["ok"] is False:
            raise FirmwareError(str(response["error"] or "unknown_error"), str(response["raw"]))
        if expected_cmd == "status" and response["cmd"] == "status":
            return response
        if response["ok"] is True and response["cmd"] == expected_cmd:
            return response

    raise TimeoutError(f"timed out waiting for {expected_cmd!r} response after {timeout:.2f}s")


def _add_command_parsers(subparsers: argparse._SubParsersAction) -> dict[str, CommandBuilder]:
    builders: dict[str, CommandBuilder] = {}

    def add(name: str, builder: CommandBuilder):
        builders[name] = builder
        return subparsers.add_parser(name)

    add("ping", lambda args: build_ping())
    add("status", lambda args: build_status())
    add("stand", lambda args: build_stand())
    add("sit", lambda args: build_sit())

    parser = add("stop", lambda args: build_stop(mode=args.mode))
    parser.add_argument("--mode", choices=["smooth", "emergency"], default="smooth")

    parser = add(
        "gait",
        lambda args: build_gait(
            dir=args.dir,
            speed=args.speed,
            duration_ms=args.duration_ms,
            steps=args.steps,
            distance_cm=args.distance_cm,
            step_len=args.step_len,
            step_ht=args.step_ht,
        ),
    )
    parser.add_argument("dir")
    parser.add_argument("--speed", type=float, default=0.25)
    parser.add_argument("--steps", type=int)
    parser.add_argument("--duration-ms", type=int)
    parser.add_argument("--distance-cm", type=float)
    parser.add_argument("--step-len", type=float)
    parser.add_argument("--step-ht", type=float)

    parser = add("rotate", lambda args: build_rotate(dir=args.dir, cycles=args.cycles, degrees=args.degrees, continuous=args.continuous))
    parser.add_argument("dir")
    parser.add_argument("--cycles", type=int)
    parser.add_argument("--degrees", type=int)
    parser.add_argument("--continuous", action="store_true")

    parser = add("wave", lambda args: build_wave(leg=args.leg, count=args.count))
    parser.add_argument("--leg", default="RF")
    parser.add_argument("--count", type=int, default=2)

    parser = add("gesture", lambda args: build_gesture(name=args.name, intensity=args.intensity))
    parser.add_argument("name")
    parser.add_argument("--intensity", type=float, default=0.5)

    parser = add("body", lambda args: build_body(x=args.x, y=args.y, z=args.z))
    parser.add_argument("--x", type=float, default=0.0)
    parser.add_argument("--y", type=float, default=0.0)
    parser.add_argument("--z", type=float, default=0.0)

    parser = add("face", lambda args: build_face(name=args.name, duration_ms=args.duration_ms, persistent=args.persistent))
    parser.add_argument("name")
    parser.add_argument("--duration-ms", type=int)
    parser.add_argument("--persistent", action="store_true")

    add("blink", lambda args: build_blink())

    parser = add("idle", lambda args: build_idle(style=args.style))
    parser.add_argument("--style", choices=["breathing", "sway"], default="breathing")

    parser = add("lean", lambda args: build_lean(dir=args.dir, amount_mm=args.amount_mm, duration_ms=args.duration_ms))
    parser.add_argument("dir")
    parser.add_argument("--amount-mm", type=float, default=20.0)
    parser.add_argument("--duration-ms", type=int, default=400)

    parser = add("look", lambda args: build_look(dir=args.dir, duration_ms=args.duration_ms, persistent=args.persistent))
    parser.add_argument("dir")
    parser.add_argument("--duration-ms", type=int)
    parser.add_argument("--persistent", action="store_true")

    parser = add("nod", lambda args: build_nod(count=args.count))
    parser.add_argument("--count", type=int, default=2)

    parser = add("shake", lambda args: build_shake(count=args.count))
    parser.add_argument("--count", type=int, default=2)

    return builders


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate and send JSON robot commands over USB serial.")
    parser.add_argument("--port", default="/dev/ttyUSB0")
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--no-wait", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    subparsers = parser.add_subparsers(dest="command", required=True)
    parser.set_defaults(command_builders=_add_command_parsers(subparsers))
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    builder = args.command_builders[args.command]

    try:
        command = builder(args)
    except BridgeError as exc:
        print(f"validation error: {exc}", file=sys.stderr)
        return 1

    payload = _json_dumps(command)
    if args.dry_run:
        print(payload)
        return 0

    bridge = SerialRobotBridge(port=args.port, baudrate=args.baudrate, timeout=args.timeout)
    try:
        bridge.connect()
        _read_until_ready(bridge, args.timeout, args.verbose)
        print(f">>> {payload}")
        bridge.send_command(command)
        if not args.no_wait:
            _read_until_response(bridge, command, args.timeout, args.verbose)
    except BridgeError as exc:
        print(f"bridge error: {exc}", file=sys.stderr)
        return 2
    finally:
        bridge.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
