import unittest

from agent.agent_errors import AgentPlanParseError
from agent.agent_plan import parse_agent_plan


class AgentPlanParserTests(unittest.TestCase):
    def test_valid_final_response_plan_parses(self):
        plan = parse_agent_plan(
            '{"version": 1, "kind": "final_response", '
            '"response": {"speak": "Hello.", "emotion": "happy", "face": "happy"}}'
        )

        self.assertEqual(plan["kind"], "final_response")
        self.assertEqual(plan["response"]["speak"], "Hello.")

    def test_plain_text_raises_parse_error(self):
        with self.assertRaises(AgentPlanParseError):
            parse_agent_plan("Hello, I am not JSON.")

    def test_two_json_objects_raise_parse_error(self):
        with self.assertRaises(AgentPlanParseError):
            parse_agent_plan('{"version": 1} {"version": 1}')

    def test_markdown_fenced_output_is_stripped(self):
        plan = parse_agent_plan(
            """```json
{"version": 1, "kind": "final_response", "response": {"speak": "Hi.", "emotion": "happy", "face": "happy"}}
```"""
        )

        self.assertEqual(plan["response"]["speak"], "Hi.")


if __name__ == "__main__":
    unittest.main()

