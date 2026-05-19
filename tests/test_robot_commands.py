import pytest

from bridge.bridge_errors import AmbiguousCommandError, InvalidParameterError
from bridge.robot_commands import (
    FORBIDDEN_FIELDS,
    GAIT_DIRECTIONS,
    WAVE_LEGS,
    build_blink,
    build_body,
    build_face,
    build_gait,
    build_gesture,
    build_idle,
    build_lean,
    build_look,
    build_nod,
    build_ping,
    build_rotate,
    build_shake,
    build_sit,
    build_stand,
    build_status,
    build_stop,
    build_wave,
    degrees_to_cycles,
)


def test_build_gait_forward():
    assert build_gait("forward", speed=0.2, steps=3) == {
        "cmd": "gait",
        "dir": "forward",
        "speed": 0.2,
        "steps": 3,
    }


def test_build_gait_all_directions():
    for direction in GAIT_DIRECTIONS:
        assert build_gait(direction)["dir"] == direction


def test_build_gait_invalid_direction():
    with pytest.raises(InvalidParameterError):
        build_gait("upward")


def test_build_gait_ambiguous_steps_and_duration():
    with pytest.raises(AmbiguousCommandError):
        build_gait(steps=3, duration_ms=1000)


def test_build_gait_ambiguous_steps_and_distance():
    with pytest.raises(AmbiguousCommandError):
        build_gait(steps=3, distance_cm=10)


def test_build_gait_ambiguous_three_bounds():
    with pytest.raises(AmbiguousCommandError):
        build_gait(steps=3, duration_ms=1000, distance_cm=10)


def test_build_gait_speed_too_low():
    with pytest.raises(InvalidParameterError):
        build_gait(speed=0.0)


def test_build_gait_speed_too_high():
    with pytest.raises(InvalidParameterError):
        build_gait(speed=2.0)


def test_build_gait_negative_steps():
    with pytest.raises(InvalidParameterError):
        build_gait(steps=-1)


def test_build_rotate_left_cycles():
    assert build_rotate("left", cycles=3) == {"cmd": "rotate", "dir": "left", "cycles": 3}


def test_build_rotate_right_degrees():
    assert build_rotate("right", degrees=90)["degrees"] == 90


def test_build_rotate_continuous():
    assert build_rotate("left", continuous=True)["continuous"] is True


def test_build_rotate_invalid_direction():
    with pytest.raises(InvalidParameterError):
        build_rotate("up")


def test_build_rotate_ambiguous_cycles_and_degrees():
    with pytest.raises(AmbiguousCommandError):
        build_rotate(cycles=1, degrees=90)


def test_build_rotate_ambiguous_degrees_and_continuous():
    with pytest.raises(AmbiguousCommandError):
        build_rotate(degrees=90, continuous=True)


def test_degrees_to_cycles_exact():
    assert degrees_to_cycles(90) == 3
    assert degrees_to_cycles(180) == 6


def test_degrees_to_cycles_rounding():
    assert degrees_to_cycles(45) == 2


def test_build_wave_valid_legs():
    for leg in WAVE_LEGS:
        assert build_wave(leg.lower())["leg"] == leg


def test_build_wave_invalid_leg():
    with pytest.raises(InvalidParameterError):
        build_wave("XX")


def test_build_wave_count_out_of_range():
    with pytest.raises(InvalidParameterError):
        build_wave(count=0)
    with pytest.raises(InvalidParameterError):
        build_wave(count=7)


def test_build_gesture_intensity_bounds():
    assert build_gesture("happy", 0.0)["intensity"] == 0.0
    assert build_gesture("happy", 1.0)["intensity"] == 1.0
    with pytest.raises(InvalidParameterError):
        build_gesture("happy", 1.1)


def test_build_body_offset_bounds():
    assert build_body(50, -50, 0)["cmd"] == "body"
    with pytest.raises(InvalidParameterError):
        build_body(x=51)
    with pytest.raises(InvalidParameterError):
        build_body(y=-51)


def test_build_stop_invalid_mode():
    with pytest.raises(InvalidParameterError):
        build_stop("fast")


def test_build_idle_invalid_style():
    with pytest.raises(InvalidParameterError):
        build_idle("bounce")


def test_no_raw_servo_fields():
    commands = [
        build_ping(),
        build_status(),
        build_stand(),
        build_sit(),
        build_stop(),
        build_gait(),
        build_rotate(),
        build_wave(),
        build_gesture(),
        build_body(),
        build_face(),
        build_blink(),
        build_idle(),
        build_lean(),
        build_look(),
        build_nod(),
        build_shake(),
    ]
    for command in commands:
        assert FORBIDDEN_FIELDS.isdisjoint(command)
