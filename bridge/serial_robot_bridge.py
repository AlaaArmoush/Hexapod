from __future__ import annotations

import json
import time
from typing import Any

import serial

from .bridge_errors import ConnectionError, FirmwareError, InvalidParameterError, NotConnectedError, TimeoutError
from .response_parser import ParsedResponse, parse_line
from .robot_commands import FORBIDDEN_FIELDS


class SerialRobotBridge:
    def __init__(self, port: str = "/dev/ttyUSB0", baudrate: int = 115200, timeout: float = 1.0):
        self._port = port
        self._baudrate = baudrate
        self._timeout = timeout
        self._serial: serial.Serial | None = None

    def connect(self) -> None:
        try:
            self._serial = serial.Serial(self._port, self._baudrate, timeout=self._timeout)
        except serial.SerialException as exc:
            raise ConnectionError(f"failed to open serial port {self._port!r}: {exc}") from exc

    def close(self) -> None:
        if self._serial is None:
            return
        try:
            if self._serial.is_open:
                self._serial.close()
        finally:
            self._serial = None

    def is_connected(self) -> bool:
        return self._serial is not None and bool(self._serial.is_open)

    def send_command(self, command_dict: dict[str, Any]) -> None:
        if not self.is_connected():
            raise NotConnectedError("serial port is not connected")
        self._validate_safe_command(command_dict)

        try:
            payload = json.dumps(command_dict, separators=(",", ":")).encode("utf-8") + b"\n"
            self._serial.write(payload)
            self._serial.flush()
        except serial.SerialException as exc:
            raise ConnectionError(f"failed to write command to serial port: {exc}") from exc

    def read_line(self) -> str | None:
        if not self.is_connected():
            raise NotConnectedError("serial port is not connected")
        try:
            raw_line = self._serial.readline()
        except serial.SerialException as exc:
            raise ConnectionError(f"failed to read from serial port: {exc}") from exc
        if raw_line == b"":
            return None
        return raw_line.decode("utf-8", errors="replace").strip()

    def read_json_line(self) -> ParsedResponse | None:
        raw_line = self.read_line()
        if raw_line is None:
            return None
        return parse_line(raw_line)

    def wait_for_ready(self, timeout: float = 5.0) -> ParsedResponse:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            response = self.read_json_line()
            if response is None or response["json"] is None:
                continue
            if response["event"] == "ready":
                return response
        raise TimeoutError(f"timed out waiting for ready event after {timeout:.2f}s")

    def wait_for_ok(self, cmd: str | None = None, timeout: float = 2.0) -> ParsedResponse:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            response = self.read_json_line()
            if response is None or response["json"] is None:
                continue

            if response["ok"] is False:
                raise FirmwareError(str(response["error"] or "unknown_error"), str(response["raw"]))
            if response["ok"] is True and (cmd is None or response["cmd"] == cmd):
                return response

        if cmd is None:
            raise TimeoutError(f"timed out waiting for ok response after {timeout:.2f}s")
        raise TimeoutError(f"timed out waiting for ok response for {cmd!r} after {timeout:.2f}s")

    def wait_for_status(self, timeout: float = 2.0) -> ParsedResponse:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            response = self.read_json_line()
            if response is None or response["json"] is None:
                continue
            if response["cmd"] == "status":
                return response
        raise TimeoutError(f"timed out waiting for status response after {timeout:.2f}s")

    def _validate_safe_command(self, command_dict: dict[str, Any]) -> None:
        if not isinstance(command_dict, dict):
            raise InvalidParameterError(f"command must be a dict, got {command_dict!r}")

        forbidden_path = self._find_forbidden_field(command_dict)
        if forbidden_path is not None:
            raise InvalidParameterError(f"command contains forbidden raw-control field: {forbidden_path}")

    def _find_forbidden_field(self, value: Any, path: str = "") -> str | None:
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = f"{path}.{key}" if path else str(key)
                if key in FORBIDDEN_FIELDS:
                    return child_path
                nested = self._find_forbidden_field(child, child_path)
                if nested is not None:
                    return nested
        elif isinstance(value, list):
            for index, child in enumerate(value):
                nested = self._find_forbidden_field(child, f"{path}[{index}]")
                if nested is not None:
                    return nested
        return None
