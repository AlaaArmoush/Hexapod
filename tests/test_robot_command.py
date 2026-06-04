import unittest

from bridge import AmbiguousCommandError, InvalidParameterError

from agent.agent_errors import UnknownActionError, UnsafeAgentPlanError
from agent.prompts import SYSTEM_PROMPT
from agent.robot_command import compile_robot_command


class RobotCommandTests(unittest.TestCase):
    def test_unified_prompt_contains_robot_command_tool_examples(self):
        self.assertIn('"name":"robot_command"', SYSTEM_PROMPT)
        self.assertIn('"cmd":"wave"', SYSTEM_PROMPT)
        self.assertIn('"cmd":"gait"', SYSTEM_PROMPT)
        self.assertIn('"cmd":"rotate"', SYSTEM_PROMPT)
        self.assertIn('"cmd":"status"', SYSTEM_PROMPT)

    def test_compile_wave_command_returns_validated_bridge_json(self):
        command = compile_robot_command({"cmd": "wave", "leg": "rf", "count": 2})

        self.assertEqual(command, {"cmd": "wave", "leg": "RF", "count": 2})

    def test_compile_gait_with_invalid_direction_raises_bridge_error(self):
        with self.assertRaises(InvalidParameterError):
            compile_robot_command({"cmd": "gait", "dir": "sideways"})

    def test_compile_gait_defaults_to_conservative_llm_speed(self):
        command = compile_robot_command({"cmd": "gait", "dir": "forward", "steps": 1})

        self.assertEqual(command, {"cmd": "gait", "dir": "forward", "speed": 0.03, "steps": 1})

    def test_compile_gait_with_ambiguous_bounds_raises_bridge_error(self):
        with self.assertRaises(AmbiguousCommandError):
            compile_robot_command(
                {"cmd": "gait", "dir": "forward", "steps": 2, "duration_ms": 500}
            )

    def test_compile_unsafe_field_raises_unsafe_error(self):
        with self.assertRaises(UnsafeAgentPlanError):
            compile_robot_command({"cmd": "wave", "raw_servo": 12})

    def test_compile_unknown_command_is_blocked(self):
        with self.assertRaises(UnknownActionError):
            compile_robot_command({"cmd": "unknown"})

    def test_compile_continuous_rotation_is_blocked(self):
        with self.assertRaises(UnknownActionError):
            compile_robot_command({"cmd": "rotate", "dir": "right", "continuous": True})

    def test_compile_rotate_degrees_converts_to_cycles(self):
        command = compile_robot_command({"cmd": "rotate", "dir": "right", "degrees": 90})

        self.assertEqual(command, {"cmd": "rotate", "dir": "right", "cycles": 3})

    def test_compile_unexpected_argument_is_blocked(self):
        with self.assertRaises(UnknownActionError):
            compile_robot_command({"cmd": "wave", "leg": "RF", "count": 2, "mood": "happy"})

    def test_compile_additional_supported_commands(self):
        self.assertEqual(compile_robot_command({"cmd": "ping"}), {"cmd": "ping"})
        self.assertEqual(compile_robot_command({"cmd": "blink"}), {"cmd": "blink"})
        self.assertEqual(compile_robot_command({"cmd": "idle", "style": "sway"}), {"cmd": "idle", "style": "sway"})
        self.assertEqual(compile_robot_command({"cmd": "look", "dir": "center"}), {"cmd": "look", "dir": "center"})
        self.assertEqual(compile_robot_command({"cmd": "nod", "count": 2}), {"cmd": "nod", "count": 2})
        self.assertEqual(
            compile_robot_command({"cmd": "camera_pan", "pos": "front_right"}),
            {"cmd": "camera_pan", "pos": "front_right"},
        )
        self.assertEqual(compile_robot_command({"cmd": "camera_center"}), {"cmd": "camera_center"})


if __name__ == "__main__":
    unittest.main()
