from unittest.mock import Mock

import pytest

from bridge.bridge_errors import ConnectionError, FirmwareError, InvalidParameterError, NotConnectedError, TimeoutError
from bridge.serial_robot_bridge import SerialRobotBridge


class FakeSerial:
    def __init__(self, lines=None):
        self.is_open = True
        self.lines = list(lines or [])
        self.writes = []
        self.flushed = False
        self.closed = False

    def write(self, payload):
        self.writes.append(payload)

    def flush(self):
        self.flushed = True

    def readline(self):
        if self.lines:
            return self.lines.pop(0)
        return b""

    def close(self):
        self.is_open = False
        self.closed = True


def connected_bridge(fake_serial=None):
    bridge = SerialRobotBridge()
    bridge._serial = fake_serial or FakeSerial()
    return bridge


def bridge_with_ok(cmd, extra=b""):
    suffix = b"," + extra if extra else b""
    return connected_bridge(FakeSerial([b'{"ok":true,"cmd":"' + cmd.encode("utf-8") + b'"' + suffix + b"}\n"]))


def test_connect_opens_serial(monkeypatch):
    serial_ctor = Mock(return_value=FakeSerial())
    monkeypatch.setattr("bridge.serial_robot_bridge.serial.Serial", serial_ctor)

    bridge = SerialRobotBridge("/dev/test", 115200, timeout=0.25)
    bridge.connect()

    assert bridge.is_connected()
    serial_ctor.assert_called_once_with("/dev/test", 115200, timeout=0.25)


def test_connect_wraps_serial_exception(monkeypatch):
    import bridge.serial_robot_bridge as serial_robot_bridge

    def raise_serial_exception(*args, **kwargs):
        raise serial_robot_bridge.serial.SerialException("missing port")

    monkeypatch.setattr("bridge.serial_robot_bridge.serial.Serial", raise_serial_exception)

    with pytest.raises(ConnectionError):
        SerialRobotBridge("/dev/missing").connect()


def test_close_is_safe_when_not_connected():
    bridge = SerialRobotBridge()
    bridge.close()
    assert not bridge.is_connected()


def test_close_closes_open_serial():
    fake = FakeSerial()
    bridge = connected_bridge(fake)
    bridge.close()
    assert fake.closed
    assert not bridge.is_connected()


def test_send_command_writes_compact_json_line():
    fake = FakeSerial()
    bridge = connected_bridge(fake)

    bridge.send_command({"cmd": "stand"})

    assert fake.writes == [b'{"cmd":"stand"}\n']
    assert fake.flushed


def test_send_command_requires_connection():
    with pytest.raises(NotConnectedError):
        SerialRobotBridge().send_command({"cmd": "stand"})


def test_send_command_rejects_raw_servo_fields():
    bridge = connected_bridge()

    with pytest.raises(InvalidParameterError):
        bridge.send_command({"cmd": "body", "servo": 1})


def test_send_command_rejects_nested_raw_servo_fields():
    bridge = connected_bridge()

    with pytest.raises(InvalidParameterError):
        bridge.send_command({"cmd": "body", "payload": {"angle": 90}})


def test_read_line_decodes_and_strips_line():
    bridge = connected_bridge(FakeSerial([b'{"ok":true}\r\n']))

    assert bridge.read_line() == '{"ok":true}'


def test_read_line_returns_none_on_timeout():
    bridge = connected_bridge(FakeSerial())

    assert bridge.read_line() is None


def test_read_json_line_parses_response():
    bridge = connected_bridge(FakeSerial([b'{"ok":true,"cmd":"stand"}\n']))

    response = bridge.read_json_line()

    assert response["ok"] is True
    assert response["cmd"] == "stand"


def test_wait_for_ready_skips_debug_lines():
    bridge = connected_bridge(FakeSerial([b"[DEBUG] booting\n", b'{"event":"ready","firmware":"hexapod"}\n']))

    response = bridge.wait_for_ready(timeout=0.1)

    assert response["event"] == "ready"


def test_wait_for_ok_matches_command():
    bridge = connected_bridge(FakeSerial([b'{"ok":true,"cmd":"ping"}\n', b'{"ok":true,"cmd":"stand"}\n']))

    response = bridge.wait_for_ok("stand", timeout=0.1)

    assert response["cmd"] == "stand"


def test_wait_for_ok_raises_firmware_error():
    bridge = connected_bridge(FakeSerial([b'{"ok":false,"error":"invalid_direction"}\n']))

    with pytest.raises(FirmwareError) as exc_info:
        bridge.wait_for_ok(timeout=0.1)

    assert exc_info.value.error_code == "invalid_direction"


def test_wait_for_ok_times_out():
    bridge = connected_bridge(FakeSerial())

    with pytest.raises(TimeoutError):
        bridge.wait_for_ok(timeout=0.001)


def test_wait_for_status_returns_status_response():
    bridge = connected_bridge(FakeSerial([b'{"ok":true,"cmd":"ping"}\n', b'{"ok":true,"cmd":"status","mode":"standing"}\n']))

    response = bridge.wait_for_status(timeout=0.1)

    assert response["json"]["mode"] == "standing"


@pytest.mark.parametrize(
    ("method_name", "args", "kwargs", "expected_write", "expected_cmd"),
    [
        ("ping", (), {}, b'{"cmd":"ping"}\n', "ping"),
        ("stand", (), {}, b'{"cmd":"stand"}\n', "stand"),
        ("sit", (), {}, b'{"cmd":"sit"}\n', "sit"),
        ("stop", (), {"mode": "smooth"}, b'{"cmd":"stop","mode":"smooth"}\n', "stop"),
        ("emergency_stop", (), {}, b'{"cmd":"stop","mode":"emergency"}\n', "stop"),
        ("gait", (), {"dir": "forward", "speed": 0.1, "steps": 1}, b'{"cmd":"gait","dir":"forward","speed":0.1,"steps":1}\n', "gait"),
        ("rotate", (), {"dir": "left", "cycles": 1}, b'{"cmd":"rotate","dir":"left","cycles":1}\n', "rotate"),
        ("wave", (), {"leg": "RF", "count": 2}, b'{"cmd":"wave","leg":"RF","count":2}\n', "wave"),
        ("gesture", (), {"name": "happy", "intensity": 0.5}, b'{"cmd":"gesture","name":"happy","intensity":0.5}\n', "gesture"),
        ("body", (), {"x": 1.0, "y": 2.0, "z": 3.0}, b'{"cmd":"body","x":1.0,"y":2.0,"z":3.0}\n', "body"),
        ("face", (), {"name": "happy", "duration_ms": 1000}, b'{"cmd":"face","name":"happy","duration_ms":1000}\n', "face"),
        ("blink", (), {}, b'{"cmd":"blink"}\n', "blink"),
        ("idle", (), {"style": "breathing"}, b'{"cmd":"idle","style":"breathing"}\n', "idle"),
        ("lean", (), {"dir": "left", "amount_mm": 20.0, "duration_ms": 400}, b'{"cmd":"lean","dir":"left","amount_mm":20.0,"duration_ms":400}\n', "lean"),
        ("look", (), {"dir": "center", "persistent": True}, b'{"cmd":"look","dir":"center","persistent":true}\n', "look"),
        ("nod", (), {"count": 2}, b'{"cmd":"nod","count":2}\n', "nod"),
        ("shake", (), {"count": 2}, b'{"cmd":"shake","count":2}\n', "shake"),
    ],
)
def test_high_level_methods_send_command_and_wait_for_ok(method_name, args, kwargs, expected_write, expected_cmd):
    bridge = bridge_with_ok(expected_cmd)

    response = getattr(bridge, method_name)(*args, **kwargs)

    assert bridge._serial.writes == [expected_write]
    assert response["ok"] is True
    assert response["cmd"] == expected_cmd


def test_status_sends_status_and_waits_for_status_response():
    bridge = connected_bridge(FakeSerial([b'{"ok":true,"cmd":"ping"}\n', b'{"ok":true,"cmd":"status","mode":"standing"}\n']))

    response = bridge.status()

    assert bridge._serial.writes == [b'{"cmd":"status"}\n']
    assert response["json"]["mode"] == "standing"


def test_high_level_method_validates_before_sending():
    bridge = connected_bridge(FakeSerial([b'{"ok":true,"cmd":"gait"}\n']))

    with pytest.raises(InvalidParameterError):
        bridge.gait(dir="upward")

    assert bridge._serial.writes == []
