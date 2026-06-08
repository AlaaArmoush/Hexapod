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
        self.synced = False
        FakeBridge.instances.append(self)

    def connect(self):
        self.connected = True

    def close(self):
        self.connected = False
        self.closed = True

    def is_connected(self):
        return self.connected and not self.closed

    def send_command(self, command):
        self.commands.append(command)

    def sync(self, timeout=6.0):
        self.synced = True
        self.sync_timeout = timeout
        return {"ok": True, "cmd": "ping", "json": {"ok": True, "cmd": "ping"}}

    def wait_for_ok(self, cmd, timeout=2.0):
        self.wait_timeout = timeout
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
        self.assertTrue(bridge.synced)
        self.assertEqual(bridge.commands, [{"cmd": "wave", "leg": "RF", "count": 2}])
        self.assertTrue(bridge.closed)
        self.assertIn("robot_connect_s", result["timings"])
        self.assertIn("robot_sync_s", result["timings"])
        self.assertIn("robot_send_s", result["timings"])
        self.assertIn("robot_ack_s", result["timings"])

    def test_real_execution_can_skip_sync_for_diagnostics(self):
        executor = RobotExecutor(
            port="/dev/test",
            dry_run=False,
            bridge_factory=FakeBridge,
            confirm_callback=lambda _command: True,
            sync_robot=False,
        )

        result = executor.execute_command({"cmd": "wave", "leg": "RF", "count": 2})

        bridge = FakeBridge.instances[0]
        self.assertFalse(bridge.synced)
        self.assertTrue(result["timings"]["robot_sync_skipped"])

    def test_keep_connected_reuses_bridge_and_sync(self):
        executor = RobotExecutor(
            port="/dev/test",
            dry_run=False,
            bridge_factory=FakeBridge,
            confirm_callback=lambda _command: True,
            keep_connected=True,
        )

        first = executor.execute_command({"cmd": "wave", "leg": "RF", "count": 2})
        second = executor.execute_command({"cmd": "blink"})

        self.assertEqual(len(FakeBridge.instances), 1)
        bridge = FakeBridge.instances[0]
        self.assertFalse(bridge.closed)
        self.assertEqual(bridge.commands, [{"cmd": "wave", "leg": "RF", "count": 2}, {"cmd": "blink"}])
        self.assertIn("robot_sync_s", first["timings"])
        self.assertTrue(second["timings"]["robot_connect_reused"])
        self.assertTrue(second["timings"]["robot_sync_skipped"])
        executor.close()
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
