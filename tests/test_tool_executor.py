import os
import tempfile
import unittest
from unittest.mock import Mock, patch

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

    @patch("requests.get")
    def test_search_web_with_valid_query_calls_tool(self, mock_get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "Heading": "Hexapod",
            "AbstractText": "A hexapod robot is a six-legged robot.",
            "AbstractURL": "https://example.com/hexapod",
            "RelatedTopics": [],
        }
        mock_get.return_value = response

        results = execute_tools([{"name": "search_web", "args": {"query": "hexapod robot"}}])

        self.assertTrue(results[0]["ok"])
        self.assertEqual(results[0]["name"], "search_web")
        self.assertEqual(results[0]["display_face"], "search")
        self.assertIn("six-legged", results[0]["spoken_text"])
        mock_get.assert_called_once()

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

    def test_future_camera_status_returns_not_implemented(self):
        results = execute_tools([{"name": "camera_status", "args": {}}])

        self.assertFalse(results[0]["ok"])
        self.assertEqual(results[0]["name"], "camera_status")
        self.assertEqual(results[0]["error"], "not_implemented")

    def test_unknown_tool_name_returns_error(self):
        results = execute_tools([{"name": "make_coffee", "args": {}}])

        self.assertFalse(results[0]["ok"])
        self.assertEqual(results[0]["name"], "make_coffee")
        self.assertEqual(results[0]["error"], "unknown_tool")


if __name__ == "__main__":
    unittest.main()
