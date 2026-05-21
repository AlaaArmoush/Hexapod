import json
import subprocess
import sys
import unittest
from pathlib import Path

from agent.agent_loop import AgentLoop


REPO_ROOT = Path(__file__).resolve().parents[1]


class FakeLlamaClient:
    def __init__(self, response):
        self.response = response
        self.messages = None

    def chat(self, messages):
        self.messages = messages
        return self.response


class AgentLoopTests(unittest.TestCase):
    def test_mock_llm_mode_produces_valid_response_without_real_server(self):
        loop = AgentLoop(mock_llm=True)

        result = loop.run_once("hello")

        self.assertTrue(result["ok"])
        self.assertEqual(result["kind"], "final_response")
        self.assertEqual(result["speak"], "Mock mode active.")

    def test_run_once_with_valid_final_response_returns_speak_text(self):
        client = FakeLlamaClient(
            json.dumps(
                {
                    "version": 1,
                    "kind": "final_response",
                    "response": {"speak": "Hello there.", "emotion": "happy", "face": "happy"},
                }
            )
        )
        loop = AgentLoop(llama_client=client)

        result = loop.run_once("hello")

        self.assertTrue(result["ok"])
        self.assertEqual(result["speak"], "Hello there.")
        self.assertEqual(client.messages[0]["role"], "system")
        self.assertEqual(client.messages[1]["content"], "hello")

    def test_run_once_with_valid_tool_request_calls_tool_executor(self):
        client = FakeLlamaClient(
            json.dumps(
                {
                    "version": 1,
                    "kind": "tool_request",
                    "response": {
                        "speak": "Let me check.",
                        "emotion": "thinking",
                        "face": "clock",
                    },
                    "tools": [{"name": "get_time", "args": {}}],
                }
            )
        )
        calls = []

        def fake_tool_executor(tools):
            calls.append(tools)
            return [
                {
                    "ok": True,
                    "name": "get_time",
                    "spoken_text": "It is 4:20 PM.",
                    "data": {},
                    "display_face": "clock",
                    "error": None,
                }
            ]

        loop = AgentLoop(llama_client=client, tool_executor=fake_tool_executor)

        result = loop.run_once("what time is it?")

        self.assertTrue(result["ok"])
        self.assertEqual(calls, [[{"name": "get_time", "args": {}}]])
        self.assertEqual(result["tool_results"][0]["spoken_text"], "It is 4:20 PM.")

    def test_invalid_model_json_returns_friendly_error(self):
        loop = AgentLoop(llama_client=FakeLlamaClient("plain text, not json"))

        result = loop.run_once("hello")

        self.assertFalse(result["ok"])
        self.assertEqual(result["kind"], "error")
        self.assertIn("could not understand", result["speak"])

    def test_cli_once_mock_llm_exits_after_one_interaction(self):
        completed = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "run_agent_cli.py"),
                "--mock-llm",
                "--once",
                "hello",
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Agent: Mock mode active.", completed.stdout)
        self.assertNotIn("You:", completed.stdout)

    def test_cli_invalid_model_json_prints_friendly_error_without_traceback(self):
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from scripts.run_agent_cli import _print_result; "
                    "_print_result({'ok': False, 'speak': 'I could not understand the model response safely.', "
                    "'error': 'bad json', 'tool_results': []})"
                ),
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Agent: I could not understand", completed.stdout)
        self.assertNotIn("Traceback", completed.stderr + completed.stdout)


if __name__ == "__main__":
    unittest.main()
