import unittest
from unittest.mock import Mock, patch

import requests

from agent.llama_client import LlamaClient


class LlamaClientTests(unittest.TestCase):
    @patch("requests.post")
    def test_chat_returns_text_from_valid_response(self, mock_post):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "choices": [{"message": {"content": "Hello from Gemma."}}]
        }
        mock_post.return_value = response

        client = LlamaClient(base_url="http://example.local", timeout=7)
        result = client.chat(
            [{"role": "user", "content": "hello"}],
            temperature=0.2,
            max_tokens=32,
        )

        self.assertEqual(result, "Hello from Gemma.")
        mock_post.assert_called_once_with(
            "http://example.local/v1/chat/completions",
            json={
                "messages": [{"role": "user", "content": "hello"}],
                "temperature": 0.2,
                "max_tokens": 32,
            },
            timeout=7,
        )

    @patch("requests.post")
    def test_chat_can_enable_json_object_response_format(self, mock_post):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "choices": [{"message": {"content": "{}"}}]
        }
        mock_post.return_value = response

        client = LlamaClient()
        result = client.chat(
            [{"role": "user", "content": "json"}],
            json_object=True,
        )

        self.assertEqual(result, "{}")
        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(payload["response_format"], {"type": "json_object"})

    @patch("requests.post")
    def test_chat_connection_refused_raises_clear_connection_error(self, mock_post):
        mock_post.side_effect = requests.exceptions.ConnectionError("refused")

        client = LlamaClient()

        with self.assertRaises(ConnectionError) as raised:
            client.chat([{"role": "user", "content": "hello"}])

        message = str(raised.exception)
        self.assertIn("Could not connect to llama-server", message)
        self.assertIn("llama-server -m", message)

    @patch("requests.post")
    def test_chat_timeout_raises_clear_timeout_error(self, mock_post):
        mock_post.side_effect = requests.exceptions.Timeout("slow")

        client = LlamaClient(timeout=5)

        with self.assertRaises(TimeoutError) as raised:
            client.chat([{"role": "user", "content": "hello"}])

        message = str(raised.exception)
        self.assertIn("Timed out waiting for llama-server", message)
        self.assertIn("5 seconds", message)

    @patch("requests.post")
    def test_chat_non_200_raises_clear_error(self, mock_post):
        response = Mock()
        response.status_code = 500
        response.text = "internal error"
        mock_post.return_value = response

        client = LlamaClient()

        with self.assertRaises(RuntimeError) as raised:
            client.chat([{"role": "user", "content": "hello"}])

        message = str(raised.exception)
        self.assertIn("HTTP 500", message)
        self.assertIn("internal error", message)


if __name__ == "__main__":
    unittest.main()
