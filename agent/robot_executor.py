"""Execute validated robot commands in dry-run or hardware mode."""

from __future__ import annotations

import json
import time
from typing import Any, Callable

from bridge.serial_robot_bridge import SerialRobotBridge

from .agent_errors import UnsafeAgentPlanError
from .robot_command import compile_robot_command


CONFIRMATION_BYPASS_COMMANDS = {"status", "ping"}
MOVEMENT_CONFIRMATION_BYPASS = {("stop", "smooth"), ("stop", "emergency")}
DEFAULT_ACK_TIMEOUT_S = 2.0
DEFAULT_SYNC_TIMEOUT_S = 12.0
COMMAND_ACK_TIMEOUTS_S = {
    "stand": 10.0,
    "sit": 10.0,
    "wave": 10.0,
    "gesture": 10.0,
    "body": 8.0,
    "lean": 8.0,
    "look": 8.0,
    "nod": 8.0,
    "shake": 8.0,
    "idle": 5.0,
    "face": 5.0,
    "blink": 5.0,
    "camera_pan": 8.0,
    "camera_center": 8.0,
}


class RobotExecutor:
    def __init__(
        self,
        port: str | None = None,
        baudrate: int = 115200,
        dry_run: bool = True,
        require_confirmation: bool = True,
        bridge_factory: Callable[..., SerialRobotBridge] = SerialRobotBridge,
        confirm_callback: Callable[[dict[str, Any]], bool] | None = None,
        sync_robot: bool = True,
        keep_connected: bool = False,
    ):
        self.port = port
        self.baudrate = baudrate
        self.dry_run = dry_run
        self.require_confirmation = require_confirmation
        self.bridge_factory = bridge_factory
        self.confirm_callback = confirm_callback
        self.sync_robot = sync_robot
        self.keep_connected = keep_connected
        self._bridge: SerialRobotBridge | None = None
        self._synced = False

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
                "timings": {},
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
                "timings": {},
            }

        timings: dict[str, float | bool] = {}
        bridge = self._get_bridge(timings)
        try:
            if self.sync_robot and not self._synced:
                sync_started_at = time.perf_counter()
                self._ping_handshake(bridge)
                timings["robot_sync_s"] = time.perf_counter() - sync_started_at
                self._synced = True
            else:
                timings["robot_sync_skipped"] = True

            send_started_at = time.perf_counter()
            bridge.send_command(validated)
            timings["robot_send_s"] = time.perf_counter() - send_started_at

            ack_started_at = time.perf_counter()
            if validated["cmd"] == "status":
                response = bridge.wait_for_status()
            else:
                response = bridge.wait_for_ok(
                    validated["cmd"],
                    timeout=self._ack_timeout(validated),
                )
            timings["robot_ack_s"] = time.perf_counter() - ack_started_at
        finally:
            if not self.keep_connected:
                bridge.close()
                self._bridge = None
                self._synced = False

        return {
            "ok": True,
            "command": validated,
            "serial_json": serial_json,
            "dry_run": False,
            "sent": True,
            "response": response,
            "timings": timings,
        }

    def close(self) -> None:
        if self._bridge is None:
            return
        self._bridge.close()
        self._bridge = None
        self._synced = False

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

    def _get_bridge(self, timings: dict[str, float | bool]) -> SerialRobotBridge:
        if self._bridge is not None and self._bridge.is_connected():
            timings["robot_connect_reused"] = True
            return self._bridge

        bridge = self.bridge_factory(self.port, self.baudrate)
        connect_started_at = time.perf_counter()
        bridge.connect()
        timings["robot_connect_s"] = time.perf_counter() - connect_started_at
        self._bridge = bridge if self.keep_connected else None
        self._synced = False
        return bridge

    def _ping_handshake(self, bridge: SerialRobotBridge) -> None:
        """Retry ping until the firmware is accepting command lines.

        Commands sent during ESP32 setup can be discarded by the firmware's startup
        serial flush, so use an explicit ping sync instead of a fixed boot delay.
        """
        bridge.sync(timeout=DEFAULT_SYNC_TIMEOUT_S)

    def _ack_timeout(self, command: dict[str, Any]) -> float:
        return COMMAND_ACK_TIMEOUTS_S.get(command.get("cmd"), DEFAULT_ACK_TIMEOUT_S)
