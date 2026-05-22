import unittest

from bridge import AmbiguousCommandError, InvalidParameterError

from agent.agent_errors import UnknownActionError, UnsafeAgentPlanError
from agent.robot_command_planner import (
    ROBOT_COMMAND_PROMPT,
    RobotCommandPlanner,
    compile_robot_command,
)


class FakeLlamaClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def chat(self, messages, temperature=None, max_tokens=None, json_object=True):
        self.calls.append(
            {
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "json_object": json_object,
            }
        )
        return self.response


class RobotCommandPlannerTests(unittest.TestCase):
    def test_prompt_contains_direct_serial_command_examples(self):
        self.assertIn('{"cmd":"ping"}', ROBOT_COMMAND_PROMPT)
        self.assertIn('{"cmd":"wave"', ROBOT_COMMAND_PROMPT)
        self.assertIn('{"cmd":"gait"', ROBOT_COMMAND_PROMPT)
        self.assertIn('{"cmd":"rotate"', ROBOT_COMMAND_PROMPT)
        self.assertIn('{"cmd":"blink"}', ROBOT_COMMAND_PROMPT)
        self.assertIn('{"cmd":"lean"', ROBOT_COMMAND_PROMPT)
        self.assertIn('{"cmd":"look"', ROBOT_COMMAND_PROMPT)
        self.assertIn("gait speed must be 0.05 to 1.0", ROBOT_COMMAND_PROMPT)

    def test_plan_command_parses_mocked_rotate_command(self):
        client = FakeLlamaClient('{"cmd":"rotate","dir":"right","cycles":3}')
        planner = RobotCommandPlanner(client)

        command = planner.plan_command("turn right 90 degrees")

        self.assertEqual(command, {"cmd": "rotate", "dir": "right", "cycles": 3})
        self.assertEqual(client.calls[0]["temperature"], 0)
        self.assertEqual(client.calls[0]["max_tokens"], 80)
        self.assertTrue(client.calls[0]["json_object"])

    def test_compile_wave_command_returns_validated_bridge_json(self):
        command = compile_robot_command({"cmd": "wave", "leg": "rf", "count": 2})

        self.assertEqual(command, {"cmd": "wave", "leg": "RF", "count": 2})

    def test_compile_gait_with_invalid_direction_raises_bridge_error(self):
        with self.assertRaises(InvalidParameterError):
            compile_robot_command({"cmd": "gait", "dir": "sideways"})

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

    def test_compile_unexpected_argument_is_blocked(self):
        with self.assertRaises(UnknownActionError):
            compile_robot_command({"cmd": "wave", "leg": "RF", "count": 2, "mood": "happy"})

    def test_compile_additional_supported_commands(self):
        self.assertEqual(compile_robot_command({"cmd": "ping"}), {"cmd": "ping"})
        self.assertEqual(compile_robot_command({"cmd": "blink"}), {"cmd": "blink"})
        self.assertEqual(compile_robot_command({"cmd": "idle", "style": "sway"}), {"cmd": "idle", "style": "sway"})
        self.assertEqual(compile_robot_command({"cmd": "look", "dir": "center"}), {"cmd": "look", "dir": "center"})
        self.assertEqual(compile_robot_command({"cmd": "nod", "count": 2}), {"cmd": "nod", "count": 2})


if __name__ == "__main__":
    unittest.main()
