from __future__ import annotations

import json
import time
from typing import Any

import serial

from .bridge_errors import ConnectionError, FirmwareError, InvalidParameterError, NotConnectedError, TimeoutError
from .response_parser import ParsedResponse, parse_line
from .robot_commands import (
    FORBIDDEN_FIELDS,
    build_blink,
    build_body,
    build_camera_center,
    build_camera_pan,
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


class SerialRobotBridge:
    def __init__(self, port: str = "/dev/ttyUSB0", baudrate: int = 115200, timeout: float = 1.0):
        self._port = port
        self._baudrate = baudrate
        self._timeout = timeout
        self._serial: serial.Serial | None = None

    def connect(self) -> None:
        try:
            # Use a short per-byte timeout so read_line() can poll its own wall-clock deadline.
            ser = serial.Serial()
            ser.port = self._port
            ser.baudrate = self._baudrate
            ser.timeout = 0.1
            ser.dtr = False
            ser.rts = False
            ser.open()
            ser.reset_input_buffer()
            self._serial = ser
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

    def read_line(self, timeout: float | None = None) -> str | None:
        if not self.is_connected():
            raise NotConnectedError("serial port is not connected")
        line = bytearray()
        read_timeout = self._timeout if timeout is None else timeout
        deadline = time.monotonic() + read_timeout
        try:
            while time.monotonic() < deadline:
                b = self._serial.read(1)
                if b:
                    line.extend(b)
                    if b == b"\n":
                        break
        except serial.SerialException as exc:
            raise ConnectionError(f"failed to read from serial port: {exc}") from exc
        if not line:
            return None
        return line.decode("utf-8", errors="replace").strip()

    def read_json_line(self, timeout: float | None = None) -> ParsedResponse | None:
        raw_line = self.read_line(timeout=timeout)
        if raw_line is None:
            return None
        return parse_line(raw_line)

    def wait_for_ready(self, timeout: float = 5.0) -> ParsedResponse:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            response = self.read_json_line(timeout=min(self._timeout, max(0.0, remaining)))
            if response is None or response["json"] is None:
                continue
            if response["event"] == "ready":
                return response
        raise TimeoutError(f"timed out waiting for ready event after {timeout:.2f}s")

    def wait_for_ok(self, cmd: str | None = None, timeout: float = 2.0) -> ParsedResponse:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            response = self.read_json_line(timeout=min(self._timeout, max(0.0, remaining)))
            if response is None or response["json"] is None:
                continue

            if response["ok"] is False:
                raise FirmwareError(str(response["error"] or "unknown_error"), str(response["raw"]))
            if response["ok"] is True and (cmd is None or response["cmd"] == cmd):
                return response

        if cmd is None:
            raise TimeoutError(f"timed out waiting for ok response after {timeout:.2f}s")
        raise TimeoutError(f"timed out waiting for ok response for {cmd!r} after {timeout:.2f}s")

    def sync(self, timeout: float = 6.0, attempt_timeout: float = 0.1) -> ParsedResponse:
        deadline = time.monotonic() + timeout
        last_error: FirmwareError | None = None
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            try:
                self.send_command(build_ping())
                return self.wait_for_ok("ping", timeout=min(attempt_timeout, max(0.05, remaining)))
            except TimeoutError:
                continue
            except FirmwareError as exc:
                last_error = exc

        if last_error is not None:
            raise last_error
        raise TimeoutError(f"timed out waiting for ping sync after {timeout:.2f}s")

    def wait_for_status(self, timeout: float = 2.0) -> ParsedResponse:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            response = self.read_json_line(timeout=min(self._timeout, max(0.0, remaining)))
            if response is None or response["json"] is None:
                continue
            if response["cmd"] == "status":
                return response
        raise TimeoutError(f"timed out waiting for status response after {timeout:.2f}s")

    def ping(self) -> ParsedResponse:
        return self._send_and_wait(build_ping(), "ping")

    def status(self) -> ParsedResponse:
        self.send_command(build_status())
        return self.wait_for_status()

    def stand(self) -> ParsedResponse:
        return self._send_and_wait(build_stand(), "stand")

    def sit(self) -> ParsedResponse:
        return self._send_and_wait(build_sit(), "sit")

    def stop(self, mode: str = "smooth") -> ParsedResponse:
        return self._send_and_wait(build_stop(mode), "stop")

    def emergency_stop(self) -> ParsedResponse:
        return self.stop(mode="emergency")

    def gait(
        self,
        dir: str = "forward",
        speed: float = 0.03,
        duration_ms: int | None = None,
        steps: int | None = None,
        distance_cm: float | None = None,
        step_len: float | None = None,
        step_ht: float | None = None,
    ) -> ParsedResponse:
        command = build_gait(
            dir=dir,
            speed=speed,
            duration_ms=duration_ms,
            steps=steps,
            distance_cm=distance_cm,
            step_len=step_len,
            step_ht=step_ht,
        )
        return self._send_and_wait(command, "gait")

    def rotate(
        self,
        dir: str = "left",
        cycles: int | None = None,
        degrees: int | None = None,
        continuous: bool = False,
    ) -> ParsedResponse:
        return self._send_and_wait(build_rotate(dir=dir, cycles=cycles, degrees=degrees, continuous=continuous), "rotate")

    def wave(self, leg: str = "RF", count: int = 2) -> ParsedResponse:
        return self._send_and_wait(build_wave(leg=leg, count=count), "wave")

    def gesture(self, name: str = "happy", intensity: float = 0.5) -> ParsedResponse:
        return self._send_and_wait(build_gesture(name=name, intensity=intensity), "gesture")

    def body(self, x: float = 0.0, y: float = 0.0, z: float = 0.0) -> ParsedResponse:
        return self._send_and_wait(build_body(x=x, y=y, z=z), "body")

    def face(self, name: str = "happy", duration_ms: int | None = None, persistent: bool = False) -> ParsedResponse:
        return self._send_and_wait(build_face(name=name, duration_ms=duration_ms, persistent=persistent), "face")

    def blink(self) -> ParsedResponse:
        return self._send_and_wait(build_blink(), "blink")

    def idle(self, style: str = "breathing") -> ParsedResponse:
        return self._send_and_wait(build_idle(style=style), "idle")

    def lean(self, dir: str = "left", amount_mm: float = 20.0, duration_ms: int = 400) -> ParsedResponse:
        return self._send_and_wait(build_lean(dir=dir, amount_mm=amount_mm, duration_ms=duration_ms), "lean")

    def look(self, dir: str = "center", duration_ms: int | None = None, persistent: bool = False) -> ParsedResponse:
        return self._send_and_wait(build_look(dir=dir, duration_ms=duration_ms, persistent=persistent), "look")

    def nod(self, count: int = 2) -> ParsedResponse:
        return self._send_and_wait(build_nod(count=count), "nod")

    def shake(self, count: int = 2) -> ParsedResponse:
        return self._send_and_wait(build_shake(count=count), "shake")

    def camera_pan(self, pos: str = "center", offset: int = 0) -> ParsedResponse:
        return self._send_and_wait(build_camera_pan(pos=pos, offset=offset), "camera_pan")

    def camera_center(self, offset: int = 0) -> ParsedResponse:
        return self._send_and_wait(build_camera_center(offset=offset), "camera_center")

    def _validate_safe_command(self, command_dict: dict[str, Any]) -> None:
        if not isinstance(command_dict, dict):
            raise InvalidParameterError(f"command must be a dict, got {command_dict!r}")

        forbidden_path = self._find_forbidden_field(command_dict)
        if forbidden_path is not None:
            raise InvalidParameterError(f"command contains forbidden raw-control field: {forbidden_path}")

    def _send_and_wait(self, command: dict[str, Any], cmd: str, timeout: float | None = None) -> ParsedResponse:
        self.send_command(command)
        return self.wait_for_ok(cmd, timeout=timeout if timeout is not None else 2.0)

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
