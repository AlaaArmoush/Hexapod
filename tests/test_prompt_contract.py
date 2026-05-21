import json
import unittest

from agent.prompts import (
    ALLOWED_EMOTIONS,
    ALLOWED_FACES,
    ALLOWED_TOOLS,
    SYSTEM_PROMPT,
)
from tools import list_all


def _json_objects_in(text):
    decoder = json.JSONDecoder()
    index = 0
    objects = []

    while index < len(text):
        start = text.find("{", index)
        if start == -1:
            break
        parsed, end = decoder.raw_decode(text[start:])
        objects.append(parsed)
        index = start + end

    return objects


class PromptContractTests(unittest.TestCase):
    def test_system_prompt_is_non_empty_string(self):
        self.assertIsInstance(SYSTEM_PROMPT, str)
        self.assertTrue(SYSTEM_PROMPT.strip())

    def test_all_six_example_outputs_are_valid_json(self):
        examples = _json_objects_in(SYSTEM_PROMPT)

        self.assertEqual(len(examples), 6)
        self.assertEqual(
            [example["kind"] for example in examples],
            [
                "final_response",
                "tool_request",
                "tool_request",
                "tool_request",
                "tool_request",
                "final_response",
            ],
        )

    def test_allowed_emotions_faces_and_tools_are_non_empty_sets(self):
        self.assertIsInstance(ALLOWED_EMOTIONS, set)
        self.assertIsInstance(ALLOWED_FACES, set)
        self.assertIsInstance(ALLOWED_TOOLS, set)
        self.assertTrue(ALLOWED_EMOTIONS)
        self.assertTrue(ALLOWED_FACES)
        self.assertEqual(ALLOWED_TOOLS, {tool.name for tool in list_all()})

    def test_prompt_contains_json_contract_word(self):
        self.assertIn("JSON", SYSTEM_PROMPT)

    def test_prompt_does_not_mention_blocked_hardware_words(self):
        lowered = SYSTEM_PROMPT.lower()

        self.assertNotIn("servo", lowered)
        self.assertNotIn("serial", lowered)


if __name__ == "__main__":
    unittest.main()
