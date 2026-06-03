import os
import tempfile
import unittest
from unittest.mock import patch

from agent.tool_executor import execute_tools


class ToolExecutorTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.previous_data_dir = os.environ.get("HEXAPOD_DATA_DIR")
        os.environ["HEXAPOD_DATA_DIR"] = self.temp_dir.name

    def tearDown(self):
        if self.previous_data_dir is None:
            os.environ.pop("HEXAPOD_DATA_DIR", None)
        else:
            os.environ["HEXAPOD_DATA_DIR"] = self.previous_data_dir
        self.temp_dir.cleanup()

    def test_get_time_executes_and_returns_normalized_result(self):
        results = execute_tools([{"name": "get_time", "args": {}}])

        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]["ok"])
        self.assertEqual(results[0]["name"], "get_time")
        self.assertIn("It is", results[0]["spoken_text"])
        self.assertEqual(results[0]["display_face"], "clock")
        self.assertIsNone(results[0]["error"])

    @patch(
        "tools.web_tools._ddg_search",
        return_value=[
            {
                "title": "Hexapod",
                "url": "https://example.com/hexapod",
                "snippet": "A hexapod robot is a six-legged robot.",
                "source": "",
                "date": "",
            }
        ],
    )
    def test_search_web_with_valid_query_calls_tool(self, mock_search):
        results = execute_tools([{"name": "search_web", "args": {"query": "hexapod robot"}}])

        self.assertTrue(results[0]["ok"])
        self.assertEqual(results[0]["name"], "search_web")
        self.assertEqual(results[0]["display_face"], "search")
        self.assertIn("Hexapod", results[0]["spoken_text"])
        mock_search.assert_called_once_with("hexapod robot", news=False)

    def test_search_web_with_missing_query_returns_validation_error(self):
        results = execute_tools([{"name": "search_web", "args": {}}])

        self.assertFalse(results[0]["ok"])
        self.assertEqual(results[0]["name"], "search_web")
        self.assertEqual(results[0]["error"], "missing_query")

    def test_remember_fact_with_key_and_value_returns_ok(self):
        results = execute_tools(
            [{"name": "remember_fact", "args": {"key": "favorite_mode", "value": "wave"}}]
        )

        self.assertTrue(results[0]["ok"])
        self.assertEqual(results[0]["name"], "remember_fact")
        self.assertEqual(results[0]["display_face"], "memory")
        self.assertEqual(results[0]["data"]["key"], "favorite_mode")

    def test_capture_image_rejects_path_label(self):
        results = execute_tools([{"name": "capture_image", "args": {"label": "../x"}}])

        self.assertFalse(results[0]["ok"])
        self.assertEqual(results[0]["name"], "capture_image")
        self.assertEqual(results[0]["error"], "invalid_label")

    def test_depth_probe_rejects_unexpected_args(self):
        results = execute_tools([{"name": "depth_probe", "args": {"roi": "center"}}])

        self.assertFalse(results[0]["ok"])
        self.assertEqual(results[0]["name"], "depth_probe")
        self.assertEqual(results[0]["error"], "unexpected_args")

    def test_unknown_tool_name_returns_error(self):
        results = execute_tools([{"name": "make_coffee", "args": {}}])

        self.assertFalse(results[0]["ok"])
        self.assertEqual(results[0]["name"], "make_coffee")
        self.assertEqual(results[0]["error"], "unknown_tool")

    def test_robot_command_dry_run_returns_validated_serial_json(self):
        results = execute_tools(
            [{"name": "robot_command", "args": {"cmd": "wave", "leg": "rf", "count": 2}}]
        )

        self.assertTrue(results[0]["ok"])
        self.assertEqual(results[0]["name"], "robot_command")
        self.assertEqual(results[0]["data"]["command"], {"cmd": "wave", "leg": "RF", "count": 2})
        self.assertEqual(results[0]["data"]["serial_json"], '{"cmd":"wave","leg":"RF","count":2}')
        self.assertTrue(results[0]["data"]["dry_run"])
        self.assertFalse(results[0]["data"]["sent"])

    def test_robot_command_repairs_rotation_degrees_from_user_text(self):
        results = execute_tools(
            [{"name": "robot_command", "args": {"cmd": "rotate", "dir": "right", "cycles": 2}}],
            user_input="turn right 90 degrees",
        )

        self.assertEqual(results[0]["data"]["command"], {"cmd": "rotate", "dir": "right", "cycles": 3})
        self.assertEqual(results[0]["data"]["serial_json"], '{"cmd":"rotate","dir":"right","cycles":3}')

    def test_robot_command_repairs_default_wave_count_from_user_text(self):
        results = execute_tools(
            [{"name": "robot_command", "args": {"cmd": "wave", "leg": "RF", "count": 1}}],
            user_input="wave with the right front leg",
        )

        self.assertEqual(results[0]["data"]["command"], {"cmd": "wave", "leg": "RF", "count": 2})

    def test_robot_command_invalid_payload_returns_error(self):
        results = execute_tools(
            [{"name": "robot_command", "args": {"cmd": "rotate", "dir": "right", "continuous": True}}]
        )

        self.assertFalse(results[0]["ok"])
        self.assertEqual(results[0]["name"], "robot_command")
        self.assertEqual(results[0]["error"], "invalid_robot_command")

    def test_robot_command_can_be_explicitly_disabled(self):
        results = execute_tools(
            [{"name": "robot_command", "args": {"cmd": "status"}}],
            enable_robot=False,
        )

        self.assertFalse(results[0]["ok"])
        self.assertEqual(results[0]["error"], "robot_disabled")

    def test_only_one_robot_command_is_allowed_per_turn(self):
        results = execute_tools(
            [
                {"name": "robot_command", "args": {"cmd": "status"}},
                {"name": "robot_command", "args": {"cmd": "wave", "leg": "RF", "count": 2}},
            ]
        )

        self.assertTrue(results[0]["ok"])
        self.assertFalse(results[1]["ok"])
        self.assertEqual(results[1]["error"], "too_many_robot_commands")


if __name__ == "__main__":
    unittest.main()
