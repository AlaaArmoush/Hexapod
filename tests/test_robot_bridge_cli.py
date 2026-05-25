import json

import pytest

import test_robot_bridge_cli


class FakeBridge:
    instances = []

    def __init__(self, port="/dev/ttyUSB0", baudrate=115200, timeout=1.0):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.connected = False
        self.closed = False
        self.sent = []
        self.responses = list(self.__class__.responses)
        self.__class__.instances.append(self)

    def connect(self):
        self.connected = True

    def close(self):
        self.closed = True

    def send_command(self, command):
        self.sent.append(command)

    def read_json_line(self):
        if self.responses:
            return self.responses.pop(0)
        return None


def parsed(raw):
    obj = json.loads(raw)
    return {
        "raw": raw,
        "json": obj,
        "ok": obj.get("ok"),
        "event": obj.get("event"),
        "error": obj.get("error"),
        "cmd": obj.get("cmd"),
    }


def debug(raw):
    return {"raw": raw, "json": None, "ok": None, "event": None, "error": None, "cmd": None}


def install_fake_bridge(monkeypatch, responses):
    FakeBridge.instances = []
    FakeBridge.responses = responses
    monkeypatch.setattr(test_robot_bridge_cli, "SerialRobotBridge", FakeBridge)


def test_dry_run_prints_validated_json_without_opening_serial(monkeypatch, capsys):
    install_fake_bridge(monkeypatch, [])

    exit_code = test_robot_bridge_cli.main(["--dry-run", "gait", "forward", "--speed", "0.1", "--steps", "3"])

    assert exit_code == 0
    assert capsys.readouterr().out == '{"cmd":"gait","dir":"forward","speed":0.1,"steps":3}\n'
    assert FakeBridge.instances == []


def test_validation_error_returns_one_and_does_not_open_serial(monkeypatch, capsys):
    install_fake_bridge(monkeypatch, [])

    exit_code = test_robot_bridge_cli.main(["--dry-run", "gait", "upward"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "validation error:" in captured.err
    assert FakeBridge.instances == []


def test_cli_connects_waits_for_ready_sends_and_prints_response(monkeypatch, capsys):
    install_fake_bridge(
        monkeypatch,
        [
            parsed('{"event":"ready","firmware":"hexapod"}'),
            parsed('{"ok":true,"cmd":"stand"}'),
        ],
    )

    exit_code = test_robot_bridge_cli.main(["--port", "/dev/test", "--baudrate", "57600", "--timeout", "0.1", "stand"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert FakeBridge.instances[0].port == "/dev/test"
    assert FakeBridge.instances[0].baudrate == 57600
    assert FakeBridge.instances[0].sent == [{"cmd": "stand"}]
    assert FakeBridge.instances[0].closed
    assert '<<< {"event":"ready","firmware":"hexapod"}' in captured.out
    assert '>>> {"cmd":"stand"}' in captured.out
    assert '<<< {"ok":true,"cmd":"stand"}' in captured.out


def test_cli_uses_separate_ready_timeout(monkeypatch):
    install_fake_bridge(
        monkeypatch,
        [
            parsed('{"event":"ready","firmware":"hexapod"}'),
            parsed('{"ok":true,"cmd":"stand"}'),
        ],
    )
    ready_timeouts = []

    def fake_read_until_ready(bridge, timeout, verbose):
        ready_timeouts.append(timeout)
        return bridge.read_json_line()

    monkeypatch.setattr(test_robot_bridge_cli, "_read_until_ready", fake_read_until_ready)

    exit_code = test_robot_bridge_cli.main(["--timeout", "0.1", "--ready-timeout", "7.5", "stand"])

    assert exit_code == 0
    assert ready_timeouts == [7.5]


def test_skip_ready_sends_without_waiting_for_ready(monkeypatch, capsys):
    install_fake_bridge(monkeypatch, [parsed('{"ok":true,"cmd":"ping"}')])

    exit_code = test_robot_bridge_cli.main(["--skip-ready", "ping"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert FakeBridge.instances[0].sent == [{"cmd": "ping"}]
    assert '<<< {"event":"ready"' not in output
    assert '>>> {"cmd":"ping"}' in output


def test_no_wait_sends_without_waiting_for_command_response(monkeypatch, capsys):
    install_fake_bridge(monkeypatch, [parsed('{"event":"ready","firmware":"hexapod"}')])

    exit_code = test_robot_bridge_cli.main(["--no-wait", "sit"])

    assert exit_code == 0
    assert FakeBridge.instances[0].sent == [{"cmd": "sit"}]
    assert '>>> {"cmd":"sit"}' in capsys.readouterr().out


def test_verbose_prints_non_json_debug_lines(monkeypatch, capsys):
    install_fake_bridge(
        monkeypatch,
        [
            debug("[DEBUG] booting"),
            parsed('{"event":"ready","firmware":"hexapod"}'),
            debug("[DEBUG] standing"),
            parsed('{"ok":true,"cmd":"stand"}'),
        ],
    )

    exit_code = test_robot_bridge_cli.main(["--verbose", "stand"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "<<< [DEBUG] booting" in output
    assert "<<< [DEBUG] standing" in output


def test_non_verbose_skips_non_json_debug_lines(monkeypatch, capsys):
    install_fake_bridge(
        monkeypatch,
        [
            debug("[DEBUG] booting"),
            parsed('{"event":"ready","firmware":"hexapod"}'),
            debug("[DEBUG] standing"),
            parsed('{"ok":true,"cmd":"stand"}'),
        ],
    )

    exit_code = test_robot_bridge_cli.main(["stand"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "[DEBUG]" not in output


def test_firmware_error_returns_two(monkeypatch, capsys):
    install_fake_bridge(
        monkeypatch,
        [
            parsed('{"event":"ready","firmware":"hexapod"}'),
            parsed('{"ok":false,"error":"invalid_direction"}'),
        ],
    )

    exit_code = test_robot_bridge_cli.main(["stand"])

    assert exit_code == 2
    assert "bridge error:" in capsys.readouterr().err


def test_status_waits_for_status_response(monkeypatch, capsys):
    install_fake_bridge(
        monkeypatch,
        [
            parsed('{"event":"ready","firmware":"hexapod"}'),
            parsed('{"ok":true,"cmd":"ping"}'),
            parsed('{"ok":true,"cmd":"status","mode":"standing"}'),
        ],
    )

    exit_code = test_robot_bridge_cli.main(["status"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert '>>> {"cmd":"status"}' in output
    assert '<<< {"ok":true,"cmd":"status","mode":"standing"}' in output
