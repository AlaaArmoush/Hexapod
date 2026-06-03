import copy
import unittest

from agent.agent_errors import (
    AgentPlanValidationError,
    UnknownToolError,
    UnsafeAgentPlanError,
)
from agent.agent_validator import ValidatedAgentPlan, validate_agent_plan


def _valid_final_plan():
    return {
        "version": 1,
        "kind": "final_response",
        "response": {
            "speak": "Hello!",
            "emotion": "happy",
            "face": "happy",
        },
    }


def _valid_tool_plan():
    return {
        "version": 1,
        "kind": "tool_request",
        "response": {
            "speak": "Let me check the time for you.",
            "emotion": "thinking",
            "face": "clock",
        },
        "tools": [{"name": "get_time", "args": {}}],
    }


class AgentPlanValidatorTests(unittest.TestCase):
    def test_valid_final_response_validates_successfully(self):
        validated = validate_agent_plan(_valid_final_plan())

        self.assertIsInstance(validated, ValidatedAgentPlan)
        self.assertEqual(validated.kind, "final_response")
        self.assertEqual(validated.speak, "Hello!")
        self.assertEqual(validated.tools, [])

    def test_valid_tool_request_with_get_time_validates_successfully(self):
        validated = validate_agent_plan(_valid_tool_plan())

        self.assertEqual(validated.kind, "tool_request")
        self.assertEqual(validated.tools, [{"name": "get_time", "args": {}}])

    def test_unknown_tool_name_raises_unknown_tool_error(self):
        plan = _valid_tool_plan()
        plan["tools"][0]["name"] = "make_coffee"

        with self.assertRaises(UnknownToolError):
            validate_agent_plan(plan)

    def test_unsafe_keyword_anywhere_raises_unsafe_plan_error(self):
        plan = _valid_final_plan()
        plan["safety"] = {"note": "do not use servo values"}

        with self.assertRaises(UnsafeAgentPlanError):
            validate_agent_plan(plan)

    def test_unsafe_unknown_tool_name_raises_unsafe_plan_error_first(self):
        plan = _valid_tool_plan()
        plan["tools"][0]["name"] = "set_servo"

        with self.assertRaises(UnsafeAgentPlanError):
            validate_agent_plan(plan)

    def test_invalid_emotion_raises_validation_error(self):
        plan = _valid_final_plan()
        plan["response"]["emotion"] = "sparkly"

        with self.assertRaises(AgentPlanValidationError):
            validate_agent_plan(plan)

    def test_invalid_face_raises_validation_error(self):
        plan = _valid_final_plan()
        plan["response"]["face"] = "laser"

        with self.assertRaises(AgentPlanValidationError):
            validate_agent_plan(plan)

    def test_speak_over_240_characters_raises_validation_error(self):
        plan = _valid_final_plan()
        plan["response"]["speak"] = "x" * 241

        with self.assertRaises(AgentPlanValidationError):
            validate_agent_plan(plan)

    def test_unknown_top_level_field_raises_validation_error(self):
        plan = _valid_final_plan()
        plan["unexpected"] = True

        with self.assertRaises(AgentPlanValidationError):
            validate_agent_plan(plan)

    def test_search_web_tool_request_validates_successfully(self):
        plan = copy.deepcopy(_valid_tool_plan())
        plan["response"]["face"] = "search"
        plan["tools"] = [{"name": "search_web", "args": {"query": "hexapod robot"}}]

        validated = validate_agent_plan(plan)

        self.assertEqual(validated.tools[0]["name"], "search_web")

    def test_camera_status_tool_request_validates_successfully(self):
        plan = copy.deepcopy(_valid_tool_plan())
        plan["response"]["face"] = "camera"
        plan["tools"] = [{"name": "camera_status", "args": {}}]

        validated = validate_agent_plan(plan)

        self.assertEqual(validated.tools[0]["name"], "camera_status")

    def test_capture_image_tool_request_validates_successfully(self):
        plan = copy.deepcopy(_valid_tool_plan())
        plan["response"]["face"] = "camera"
        plan["tools"] = [{"name": "capture_image", "args": {"label": "desk_test"}}]

        validated = validate_agent_plan(plan)

        self.assertEqual(validated.tools[0]["args"]["label"], "desk_test")

    def test_depth_probe_tool_request_validates_successfully(self):
        plan = copy.deepcopy(_valid_tool_plan())
        plan["response"]["face"] = "camera"
        plan["tools"] = [{"name": "depth_probe", "args": {}}]

        validated = validate_agent_plan(plan)

        self.assertEqual(validated.tools[0]["name"], "depth_probe")

    def test_check_clearance_tool_request_validates_successfully(self):
        plan = copy.deepcopy(_valid_tool_plan())
        plan["response"]["face"] = "camera"
        plan["tools"] = [{"name": "check_clearance", "args": {"min_clear_m": 0.5, "roi": "center"}}]

        validated = validate_agent_plan(plan)

        self.assertEqual(validated.tools[0]["name"], "check_clearance")

    def test_camera_status_rejects_unexpected_args(self):
        plan = copy.deepcopy(_valid_tool_plan())
        plan["response"]["face"] = "camera"
        plan["tools"] = [{"name": "camera_status", "args": {"label": "desk"}}]

        with self.assertRaises(AgentPlanValidationError):
            validate_agent_plan(plan)

    def test_depth_probe_rejects_unexpected_args(self):
        plan = copy.deepcopy(_valid_tool_plan())
        plan["response"]["face"] = "camera"
        plan["tools"] = [{"name": "depth_probe", "args": {"roi": "center"}}]

        with self.assertRaises(AgentPlanValidationError):
            validate_agent_plan(plan)

    def test_check_clearance_rejects_bad_args(self):
        plan = copy.deepcopy(_valid_tool_plan())
        plan["response"]["face"] = "camera"
        plan["tools"] = [{"name": "check_clearance", "args": {"min_clear_m": 10.0, "roi": "wide"}}]

        with self.assertRaises(AgentPlanValidationError):
            validate_agent_plan(plan)

    def test_capture_image_rejects_path_label(self):
        plan = copy.deepcopy(_valid_tool_plan())
        plan["response"]["face"] = "camera"
        plan["tools"] = [{"name": "capture_image", "args": {"label": "../desk"}}]

        with self.assertRaises(AgentPlanValidationError):
            validate_agent_plan(plan)

    def test_robot_command_tool_request_validates_successfully(self):
        plan = copy.deepcopy(_valid_tool_plan())
        plan["response"]["face"] = "happy"
        plan["tools"] = [{"name": "robot_command", "args": {"cmd": "wave", "leg": "RF", "count": 2}}]

        validated = validate_agent_plan(plan)

        self.assertEqual(validated.kind, "tool_request")
        self.assertEqual(validated.tools[0]["name"], "robot_command")

    def test_robot_request_kind_is_rejected(self):
        plan = _valid_final_plan()
        plan["kind"] = "robot_request"

        with self.assertRaises(AgentPlanValidationError):
            validate_agent_plan(plan)

    def test_actions_top_level_field_is_rejected(self):
        plan = _valid_final_plan()
        plan["actions"] = []

        with self.assertRaises(AgentPlanValidationError):
            validate_agent_plan(plan)


if __name__ == "__main__":
    unittest.main()
