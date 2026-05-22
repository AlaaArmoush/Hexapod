"""Execute validated robot commands in dry-run or hardware mode."""

from __future__ import annotations

import json
from typing import Any, Callable

from bridge.serial_robot_bridge import SerialRobotBridge

from .agent_errors import UnsafeAgentPlanError
from .robot_command import compile_robot_command


CONFIRMATION_BYPASS_COMMANDS = {"status", "ping"}
MOVEMENT_CONFIRMATION_BYPASS = {("stop", "smooth"), ("stop", "emergency")}


class RobotExecutor:
    def __init__(
        self,
        port: str | None = None,
        baudrate: int = 115200,
        dry_run: bool = True,
        require_confirmation: bool = True,
        bridge_factory: Callable[..., SerialRobotBridge] = SerialRobotBridge,
        confirm_callback: Callable[[dict[str, Any]], bool] | None = None,
    ):
        self.port = port
        self.baudrate = baudrate
        self.dry_run = dry_run
        self.require_confirmation = require_confirmation
        self.bridge_factory = bridge_factory
        self.confirm_callback = confirm_callback

    def execute_command(self, command: dict[str, Any]) -> dict[str, Any]:
        validated = compile_robot_command(command)
        serial_json = json.dumps(validated, separators=(",", ":"))

        if self.dry_run:
            return {
                "ok": True,
                "command": validated,
                "serial_json": serial_json,
                "dry_run": True,
                "sent": False,
                "response": None,
            }

        if not self.port:
            raise UnsafeAgentPlanError("Real robot execution requires an explicit serial port")

        if self._requires_confirmation(validated) and not self._confirm(validated):
            return {
                "ok": False,
                "command": validated,
                "serial_json": serial_json,
                "dry_run": False,
                "sent": False,
                "response": None,
                "error": "confirmation_denied",
            }

        bridge = self.bridge_factory(self.port, self.baudrate)
        try:
            bridge.connect()
            bridge.send_command(validated)
            if validated["cmd"] == "status":
                response = bridge.wait_for_status()
            else:
                response = bridge.wait_for_ok(validated["cmd"])
        finally:
            bridge.close()

        return {
            "ok": True,
            "command": validated,
            "serial_json": serial_json,
            "dry_run": False,
            "sent": True,
            "response": response,
        }

    def _requires_confirmation(self, command: dict[str, Any]) -> bool:
        if not self.require_confirmation:
            return False
        cmd = command.get("cmd")
        if cmd in CONFIRMATION_BYPASS_COMMANDS:
            return False
        if (cmd, command.get("mode", "smooth")) in MOVEMENT_CONFIRMATION_BYPASS:
            return False
        return True

    def _confirm(self, command: dict[str, Any]) -> bool:
        if self.confirm_callback is None:
            return False
        return bool(self.confirm_callback(command))
