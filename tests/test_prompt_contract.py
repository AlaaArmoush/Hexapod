import json
import unittest

from agent.prompts import (
    ALLOWED_EMOTIONS,
    ALLOWED_FACES,
    ALLOWED_TOOLS,
    RUNTIME_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
)
from agent.response_contract import FIRMWARE_COMPATIBLE_FACES, TOOL_RECOMMENDED_FACES
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

    def test_example_outputs_in_prompt_are_valid_json(self):
        examples = _json_objects_in(SYSTEM_PROMPT)

        self.assertGreaterEqual(len(examples), 2)
        self.assertEqual(examples[0]["kind"], "final_response")
        self.assertEqual(examples[1]["kind"], "tool_request")

    def test_allowed_emotions_faces_and_tools_are_non_empty_sets(self):
        self.assertIsInstance(ALLOWED_EMOTIONS, set)
        self.assertIsInstance(ALLOWED_FACES, set)
        self.assertIsInstance(ALLOWED_TOOLS, set)
        self.assertTrue(ALLOWED_EMOTIONS)
        self.assertTrue(ALLOWED_FACES)
        self.assertEqual(ALLOWED_TOOLS, {tool.name for tool in list_all()} | {"robot_command"})

    def test_tool_recommended_faces_are_allowed_and_firmware_compatible(self):
        self.assertTrue(TOOL_RECOMMENDED_FACES)
        self.assertLessEqual(TOOL_RECOMMENDED_FACES, ALLOWED_FACES)
        self.assertLessEqual(TOOL_RECOMMENDED_FACES, FIRMWARE_COMPATIBLE_FACES)

    def test_all_firmware_compatible_faces_are_allowed(self):
        self.assertEqual(ALLOWED_FACES, FIRMWARE_COMPATIBLE_FACES)

    def test_prompt_contains_json_contract_word(self):
        self.assertIn("JSON", SYSTEM_PROMPT)

    def test_prompt_contains_camera_tool_examples(self):
        self.assertIn('"name":"camera_status"', SYSTEM_PROMPT)
        self.assertIn('"name":"capture_image"', SYSTEM_PROMPT)
        self.assertIn('"name":"depth_probe"', SYSTEM_PROMPT)
        self.assertIn('"label":"desk_test"', SYSTEM_PROMPT)

    def test_runtime_prompt_is_the_unified_system_prompt(self):
        self.assertEqual(RUNTIME_SYSTEM_PROMPT, SYSTEM_PROMPT)

    def test_prompt_does_not_mention_blocked_hardware_words(self):
        lowered = SYSTEM_PROMPT.lower()

        self.assertNotIn("servo", lowered)
        self.assertNotIn("raw_servo", lowered)


if __name__ == "__main__":
    unittest.main()
