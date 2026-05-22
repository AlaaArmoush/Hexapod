import json
import subprocess
import sys
import unittest
from pathlib import Path

from agent.agent_loop import AgentLoop
from scripts.run_agent_cli import _build_loop, _print_result, build_parser


REPO_ROOT = Path(__file__).resolve().parents[1]


class FakeLlamaClient:
    def __init__(self, response):
        self.responses = response if isinstance(response, list) else [response]
        self.messages = None
        self.calls = []
        self.chat_kwargs = []

    def chat(self, messages, temperature=None, max_tokens=None, json_object=True):
        self.messages = messages
        self.calls.append(messages)
        self.chat_kwargs.append(
            {
                "temperature": temperature,
                "max_tokens": max_tokens,
                "json_object": json_object,
            }
        )
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


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
        self.assertEqual(
            client.chat_kwargs[0],
            {"temperature": 0, "max_tokens": 80, "json_object": False},
        )

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

        def fake_tool_executor(tools, **_kwargs):
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

        loop = AgentLoop(
            llama_client=client,
            tool_executor=fake_tool_executor,
        )

        result = loop.run_once("what time is it?")

        self.assertTrue(result["ok"])
        self.assertEqual(calls, [[{"name": "get_time", "args": {}}]])
        self.assertEqual(result["tool_results"][0]["spoken_text"], "It is 4:20 PM.")

    def test_summarize_tool_results_rewrites_successful_tool_text(self):
        client = FakeLlamaClient(
            [
                json.dumps(
                    {
                        "version": 1,
                        "kind": "tool_request",
                        "response": {
                            "speak": "Let me search.",
                            "emotion": "thinking",
                            "face": "search",
                        },
                        "tools": [{"name": "search_web", "args": {"query": "hexapod"}}],
                    }
                ),
                "Hexapod robots are six-legged walking machines.",
            ]
        )

        def fake_tool_executor(_tools, **_kwargs):
            return [
                {
                    "ok": True,
                    "name": "search_web",
                    "spoken_text": "Raw snippet text.",
                    "data": {"results": [{"title": "Hexapod", "snippet": "Raw snippet text."}]},
                    "display_face": "search",
                    "error": None,
                }
            ]

        loop = AgentLoop(
            llama_client=client,
            tool_executor=fake_tool_executor,
            summarize_tool_results=True,
        )

        result = loop.run_once("search hexapod")

        self.assertTrue(result["ok"])
        self.assertEqual(
            result["tool_results"][0]["spoken_text"],
            "Hexapod robots are six-legged walking machines.",
        )
        self.assertTrue(result["tool_results"][0]["summarized"])
        self.assertEqual(len(client.calls), 2)

    def test_summarize_tool_results_falls_back_when_second_model_call_fails(self):
        client = FakeLlamaClient(
            [
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
                ),
                RuntimeError("summary failed"),
            ]
        )

        def fake_tool_executor(_tools, **_kwargs):
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

        loop = AgentLoop(
            llama_client=client,
            tool_executor=fake_tool_executor,
            summarize_tool_results=True,
        )

        result = loop.run_once("what time is it?")

        self.assertTrue(result["ok"])
        self.assertEqual(result["tool_results"][0]["spoken_text"], "It is 4:20 PM.")
        self.assertNotIn("summarized", result["tool_results"][0])

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

    def test_cli_enable_robot_requires_port(self):
        args = build_parser().parse_args(["--enable-robot", "--once", "wave"])

        with self.assertRaises(SystemExit):
            _build_loop(args)

    def test_cli_prints_robot_serial_json(self):
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from scripts.run_agent_cli import _print_result; "
                    "_print_result({'ok': True, 'speak': '', 'tool_results': ["
                    "{'ok': True, 'name': 'robot_command', 'spoken_text': 'Robot command dry-run validated.', "
                    "'data': {'serial_json': '{\"cmd\":\"wave\"}', 'dry_run': True}, 'error': None}"
                    "]})"
                ),
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn('Robot JSON [DRY-RUN]: {"cmd":"wave"}', completed.stdout)


if __name__ == "__main__":
    unittest.main()
