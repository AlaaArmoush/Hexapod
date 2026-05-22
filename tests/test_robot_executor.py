import unittest

from agent.agent_errors import UnsafeAgentPlanError
from agent.agent_errors import UnknownActionError
from agent.robot_executor import RobotExecutor


class FakeBridge:
    instances = []

    def __init__(self, port, baudrate):
        self.port = port
        self.baudrate = baudrate
        self.connected = False
        self.closed = False
        self.commands = []
        FakeBridge.instances.append(self)

    def connect(self):
        self.connected = True

    def close(self):
        self.closed = True

    def send_command(self, command):
        self.commands.append(command)

    def wait_for_ok(self, cmd):
        return {"ok": True, "cmd": cmd, "json": {"ok": True, "cmd": cmd}}

    def wait_for_status(self):
        return {"ok": True, "cmd": "status", "json": {"ok": True, "cmd": "status"}}


class RobotExecutorTests(unittest.TestCase):
    def setUp(self):
        FakeBridge.instances = []

    def test_dry_run_validates_and_does_not_open_serial(self):
        executor = RobotExecutor(dry_run=True, bridge_factory=FakeBridge)

        result = executor.execute_command({"cmd": "wave", "leg": "rf", "count": 2})

        self.assertTrue(result["ok"])
        self.assertTrue(result["dry_run"])
        self.assertFalse(result["sent"])
        self.assertEqual(result["command"], {"cmd": "wave", "leg": "RF", "count": 2})
        self.assertEqual(result["serial_json"], '{"cmd":"wave","leg":"RF","count":2}')
        self.assertEqual(FakeBridge.instances, [])

    def test_real_execution_requires_port(self):
        executor = RobotExecutor(dry_run=False, bridge_factory=FakeBridge)

        with self.assertRaises(UnsafeAgentPlanError):
            executor.execute_command({"cmd": "status"})

    def test_unsafe_command_is_rejected_before_serial(self):
        executor = RobotExecutor(dry_run=False, port="/dev/test", bridge_factory=FakeBridge)

        with self.assertRaises(UnsafeAgentPlanError):
            executor.execute_command({"cmd": "wave", "raw_servo": 12})

        self.assertEqual(FakeBridge.instances, [])

    def test_unknown_command_is_rejected_before_serial(self):
        executor = RobotExecutor(dry_run=False, port="/dev/test", bridge_factory=FakeBridge)

        with self.assertRaises(UnknownActionError):
            executor.execute_command({"cmd": "dance"})

        self.assertEqual(FakeBridge.instances, [])

    def test_confirmation_denial_blocks_movement_before_serial(self):
        executor = RobotExecutor(
            port="/dev/test",
            dry_run=False,
            bridge_factory=FakeBridge,
            confirm_callback=lambda _command: False,
        )

        result = executor.execute_command({"cmd": "wave", "leg": "RF", "count": 2})

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "confirmation_denied")
        self.assertFalse(result["sent"])
        self.assertEqual(FakeBridge.instances, [])

    def test_real_execution_sends_after_confirmation(self):
        executor = RobotExecutor(
            port="/dev/test",
            dry_run=False,
            bridge_factory=FakeBridge,
            confirm_callback=lambda _command: True,
        )

        result = executor.execute_command({"cmd": "wave", "leg": "RF", "count": 2})

        self.assertTrue(result["ok"])
        self.assertFalse(result["dry_run"])
        self.assertTrue(result["sent"])
        bridge = FakeBridge.instances[0]
        self.assertEqual(bridge.commands, [{"cmd": "wave", "leg": "RF", "count": 2}])
        self.assertTrue(bridge.closed)

    def test_stop_bypasses_confirmation(self):
        executor = RobotExecutor(
            port="/dev/test",
            dry_run=False,
            bridge_factory=FakeBridge,
            confirm_callback=lambda _command: False,
        )

        result = executor.execute_command({"cmd": "stop"})

        self.assertTrue(result["ok"])
        self.assertTrue(result["sent"])
        self.assertEqual(FakeBridge.instances[0].commands, [{"cmd": "stop", "mode": "smooth"}])

    def test_status_bypasses_confirmation_and_waits_for_status(self):
        executor = RobotExecutor(
            port="/dev/test",
            dry_run=False,
            bridge_factory=FakeBridge,
            confirm_callback=lambda _command: False,
        )

        result = executor.execute_command({"cmd": "status"})

        self.assertTrue(result["ok"])
        self.assertEqual(result["response"]["cmd"], "status")


if __name__ == "__main__":
    unittest.main()
