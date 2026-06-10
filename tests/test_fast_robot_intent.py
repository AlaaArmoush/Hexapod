from agent.fast_robot_intent import build_fast_robot_plan


def command_for(text):
    plan = build_fast_robot_plan(text)
    assert plan is not None
    return plan["tools"][0]["args"]


def test_step_forward_maps_to_one_step_gait():
    assert command_for("step forward a bit") == {
        "cmd": "gait",
        "dir": "forward",
        "speed": 0.06,
        "steps": 1,
    }


def test_step_back_maps_to_backward_gait():
    assert command_for("step back")["dir"] == "backward"


def test_diagonal_direction_is_not_reduced_to_forward():
    assert command_for("take two steps forward left") == {
        "cmd": "gait",
        "dir": "forward_left",
        "speed": 0.06,
        "steps": 2,
    }


def test_turn_right_uses_rotate_command():
    assert command_for("turn right 90 degrees") == {"cmd": "rotate", "dir": "right", "degrees": 90}


def test_question_does_not_shortcut():
    assert build_fast_robot_plan("how do I step forward?") is None
