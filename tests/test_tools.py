import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools import (
    TOOL_REGISTRY,
    ToolMeta,
    ToolResult,
    call_tool,
    get_date,
    get_time,
    get_tool,
    list_all,
    list_implemented,
    search_web,
)


EXPECTED_TOOL_NAMES = {
    "get_time",
    "get_date",
    "search_web",
    "remember_fact",
    "recall_memory",
    "forget_memory",
    "system_status",
    "network_status",
    "battery_status",
    "set_timer",
    "set_reminder",
    "capture_image",
    "describe_scene",
    "detect_person",
    "detect_object",
    "mic_status",
    "voice_direction_estimate",
    "camera_status",
    "tell_joke",
    "local_file_lookup",
    "read_project_note",
    "explain_capability",
}

IMPLEMENTED_TOOL_NAMES = {
    "get_time",
    "get_date",
    "search_web",
    "remember_fact",
    "recall_memory",
    "forget_memory",
    "system_status",
    "network_status",
    "battery_status",
    "set_timer",
    "set_reminder",
    "capture_image",
    "camera_status",
}

UNIMPLEMENTED_TOOL_NAMES = EXPECTED_TOOL_NAMES - IMPLEMENTED_TOOL_NAMES


class ToolContractTests(unittest.TestCase):
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

    def test_tool_result_serialization(self):
        result = ToolResult(
            ok=True,
            action="example_action",
            spoken_text="Done.",
            data={"answer": 42},
            display_face="success",
            display_duration_ms=None,
        )

        serialized = result.to_dict()
        self.assertEqual(serialized["ok"], True)
        self.assertEqual(serialized["action"], "example_action")
        self.assertEqual(serialized["spoken_text"], "Done.")
        self.assertEqual(serialized["data"], {"answer": 42})
        self.assertEqual(serialized["display_face"], "success")
        self.assertIsNone(serialized["display_duration_ms"])
        self.assertIsNone(serialized["error"])
        self.assertEqual(json.loads(json.dumps(serialized)), serialized)

    def test_registry_completeness(self):
        names = {tool.name for tool in TOOL_REGISTRY}
        self.assertEqual(names, EXPECTED_TOOL_NAMES)
        self.assertEqual(len(TOOL_REGISTRY), 22)

        for tool in TOOL_REGISTRY:
            self.assertIsInstance(tool, ToolMeta)
            self.assertTrue(tool.description)
            self.assertTrue(tool.recommended_display_face)
            self.assertIsNotNone(tool.fn)

    def test_lookup_helpers(self):
        self.assertEqual(len(list_all()), 22)
        self.assertEqual({tool.name for tool in list_implemented()}, IMPLEMENTED_TOOL_NAMES)
        self.assertEqual(get_tool(" GET_TIME ").name, "get_time")
        self.assertIsNone(get_tool("missing_tool"))

    def test_get_time_ok(self):
        result = get_time()
        self.assertTrue(result.ok)
        self.assertEqual(result.display_face, "clock")
        self.assertIsInstance(result.data["hour"], int)

    def test_get_date_ok(self):
        result = get_date()
        self.assertTrue(result.ok)
        self.assertEqual(result.display_face, "calendar")
        self.assertIsInstance(result.data["year"], int)

    def test_search_web_empty_query(self):
        result = search_web("   ")
        self.assertFalse(result.ok)
        self.assertEqual(result.error, "invalid_query")
        self.assertEqual(result.display_face, "search")

    @patch("tools.web_tools._ddg_search")
    def test_search_web_network_failure(self, mock_search):
        mock_search.side_effect = RuntimeError("offline")
        result = search_web("hexapod robot")

        self.assertFalse(result.ok)
        self.assertEqual(result.error, "network_error")
        self.assertEqual(result.data["query"], "hexapod robot")
        self.assertEqual(result.display_face, "search")

    @patch("tools.web_tools._ddg_search")
    def test_search_web_parse_error(self, mock_search):
        mock_search.side_effect = ValueError("bad json")
        result = search_web("hexapod robot")
        self.assertFalse(result.ok)
        self.assertEqual(result.error, "network_error")
        self.assertEqual(result.display_face, "search")

    @patch("tools.web_tools._ddg_search", return_value=[])
    def test_search_web_no_results(self, mock_search):
        result = search_web("unlikely local query")

        self.assertTrue(result.ok)
        self.assertEqual(result.spoken_text, "I couldn't find anything for that.")
        self.assertEqual(result.data["results"], [])
        self.assertEqual(result.display_face, "search")
        mock_search.assert_called_once_with("unlikely local query", news=False)

    @patch(
        "tools.web_tools._ddg_search",
        return_value=[
            {
                "title": "Hexapod",
                "url": "https://example.com/hexapod",
                "snippet": "A hexapod robot is a six-legged robot.",
                "source": "",
                "date": "",
            },
            {
                "title": "Robot",
                "url": "https://example.com/robot",
                "snippet": "A machine capable of carrying out tasks.",
                "source": "",
                "date": "",
            },
        ],
    )
    def test_search_web_success(self, mock_search):
        result = call_tool("search_web", query="hexapod robot")

        self.assertTrue(result.ok)
        self.assertEqual(result.display_face, "search")
        self.assertEqual(result.data["query"], "hexapod robot")
        self.assertEqual(result.data["results"][0]["title"], "Hexapod")
        self.assertIn("Hexapod", result.spoken_text)
        mock_search.assert_called_once_with("hexapod robot", news=False)

    def test_memory_roundtrip(self):
        remembered = call_tool("remember_fact", key="favorite_command", value="wave")
        self.assertTrue(remembered.ok)
        self.assertEqual(remembered.display_face, "memory")

        recalled = call_tool("recall_memory", key="favorite_command")
        self.assertTrue(recalled.ok)
        self.assertEqual(recalled.data["value"], "wave")

        forgotten = call_tool("forget_memory", key="favorite_command")
        self.assertTrue(forgotten.ok)

        missing = call_tool("recall_memory", key="favorite_command")
        self.assertFalse(missing.ok)
        self.assertEqual(missing.error, "key_not_found")

    def test_recall_missing_key(self):
        result = call_tool("recall_memory", key="missing")
        self.assertFalse(result.ok)
        self.assertEqual(result.error, "key_not_found")
        self.assertEqual(result.display_face, "memory")

    def test_system_status_structure(self):
        result = call_tool("system_status")
        self.assertTrue(result.ok)
        self.assertEqual(result.display_face, "system")
        self.assertIn("platform", result.data)
        self.assertIn("disk_used_pct", result.data)

    def test_network_status_structure(self):
        result = call_tool("network_status")
        self.assertTrue(result.ok)
        self.assertEqual(result.display_face, "wifi")
        self.assertIsInstance(result.data["connected"], bool)
        self.assertIn("latency_ms", result.data)

    def test_battery_status_structure(self):
        result = call_tool("battery_status")
        self.assertTrue(result.ok)
        self.assertEqual(result.display_face, "battery")
        self.assertFalse(result.data["implemented"])

    def test_timer_and_reminder_metadata(self):
        timer = call_tool("set_timer", label="test", duration_seconds=60)
        self.assertTrue(timer.ok)
        self.assertEqual(timer.display_face, "timer")
        self.assertEqual(timer.data["duration_s"], 60)
        self.assertIn("fires_at", timer.data)

        reminder = call_tool("set_reminder", label="test", datetime_str="2026-06-01 10:00")
        self.assertTrue(reminder.ok)
        self.assertEqual(reminder.display_face, "reminder")
        self.assertEqual(reminder.data["remind_at"], "2026-06-01T10:00:00")

    def test_invalid_timer_and_reminder_inputs(self):
        timer = call_tool("set_timer", label="bad", duration_seconds=0)
        self.assertFalse(timer.ok)
        self.assertEqual(timer.error, "invalid_duration")

        reminder = call_tool("set_reminder", label="bad", datetime_str="not-a-date")
        self.assertFalse(reminder.ok)
        self.assertEqual(reminder.error, "invalid_datetime")

    def test_unimplemented_tool(self):
        result = call_tool("describe_scene")
        self.assertFalse(result.ok)
        self.assertEqual(result.action, "describe_scene")
        self.assertEqual(result.error, "not_implemented")
        self.assertEqual(result.display_face, "camera")

    def test_registry_stubs_return_clean_tool_results(self):
        for tool in TOOL_REGISTRY:
            if tool.name not in UNIMPLEMENTED_TOOL_NAMES:
                continue
            with self.subTest(tool=tool.name):
                result = call_tool(tool.name)
                self.assertIsInstance(result, ToolResult)
                self.assertEqual(result.action, tool.name)
                self.assertEqual(result.display_face, tool.recommended_display_face)
                self.assertEqual(result.error, "not_implemented")
                self.assertFalse(result.ok)
                self.assertTrue(result.spoken_text)

    def test_unknown_tool(self):
        result = call_tool("no_such_tool")
        self.assertFalse(result.ok)
        self.assertEqual(result.action, "no_such_tool")
        self.assertEqual(result.error, "unknown_tool")
        self.assertEqual(result.display_face, "error")
        self.assertEqual(set(result.data["available_tools"]), EXPECTED_TOOL_NAMES)

    def test_cli_get_time_smoke(self):
        completed = subprocess.run(
            [sys.executable, "test_tools_cli.py", "get_time"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0)
        self.assertIn("action:        get_time", completed.stdout)
        self.assertIn("display_face:  clock", completed.stdout)


if __name__ == "__main__":
    unittest.main()
