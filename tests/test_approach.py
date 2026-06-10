import time
import unittest

from camera.approach import ApproachController, ApproachResult
from camera.tracker import TrackedPerson


def _person(x=0.0, y=0.0, area=0.1, dist=None):
    return TrackedPerson(
        frame_position_x=x, frame_position_y=y,
        confidence=0.9, distance_m=dist,
        bbox_area=area, timestamp_ms=int(time.time() * 1000),
    )


class ScriptedTracker:
    """Cycles through a list of TrackedPerson snapshots, one per target read."""

    def __init__(self, snapshots: list):
        self._snapshots = snapshots
        self._index = 0

    @property
    def target(self):
        if self._index < len(self._snapshots):
            t = self._snapshots[self._index]
            self._index += 1
            return t
        return self._snapshots[-1] if self._snapshots else None

    @property
    def lost_ms(self):
        return 0


class LostTracker:
    """Always returns None target with configurable lost_ms."""
    def __init__(self, lost_ms=3000):
        self._lost_ms = lost_ms

    @property
    def target(self): return None

    @property
    def lost_ms(self): return self._lost_ms


class ApproachTests(unittest.TestCase):
    def _controller(self, tracker):
        ctrl = ApproachController(tracker, self._commands.append)
        ctrl.STEP_WAIT_S = 0.0   # no real waiting in tests
        ctrl.TIMEOUT_S = 1.0
        return ctrl

    def setUp(self):
        self._commands = []

    def test_arrived_when_person_close_by_depth(self):
        tracker = ScriptedTracker([_person(x=0.0, dist=0.8)])
        result = self._controller(tracker).run()
        self.assertEqual(result, ApproachResult.ARRIVED)
        self.assertEqual(self._commands, [])   # already close — no movement needed

    def test_arrived_when_person_close_by_area(self):
        tracker = ScriptedTracker([_person(x=0.0, area=0.3)])
        result = self._controller(tracker).run()
        self.assertEqual(result, ApproachResult.ARRIVED)

    def test_rotates_left_when_person_is_left(self):
        # Person left, then centred and far, then close
        tracker = ScriptedTracker([
            _person(x=-0.5, area=0.05),
            _person(x=0.0,  area=0.05),
            _person(x=0.0,  area=0.3),
        ])
        result = self._controller(tracker).run()
        self.assertEqual(result, ApproachResult.ARRIVED)
        cmds = [c["cmd"] for c in self._commands]
        self.assertIn("rotate", cmds)
        rotate_cmd = next(c for c in self._commands if c["cmd"] == "rotate")
        self.assertEqual(rotate_cmd["dir"], "left")

    def test_rotates_right_when_person_is_right(self):
        tracker = ScriptedTracker([
            _person(x=0.6, area=0.05),
            _person(x=0.0, area=0.3),
        ])
        self._controller(tracker).run()
        rotate_cmd = next(c for c in self._commands if c["cmd"] == "rotate")
        self.assertEqual(rotate_cmd["dir"], "right")

    def test_walks_forward_when_centred_and_far(self):
        tracker = ScriptedTracker([
            _person(x=0.0, area=0.05),
            _person(x=0.0, area=0.3),
        ])
        result = self._controller(tracker).run()
        self.assertEqual(result, ApproachResult.ARRIVED)
        gait_cmd = next(c for c in self._commands if c["cmd"] == "gait")
        self.assertEqual(gait_cmd["dir"], "forward")

    def test_lost_when_tracker_has_no_target_long_enough(self):
        tracker = LostTracker(lost_ms=3000)
        ctrl = ApproachController(tracker, self._commands.append)
        ctrl.STEP_WAIT_S = 0.0
        ctrl.TIMEOUT_S = 5.0
        ctrl.LOST_THRESHOLD_MS = 2000
        result = ctrl.run()
        self.assertEqual(result, ApproachResult.LOST)

    def test_timeout_when_person_never_gets_close(self):
        # Person always far, never reaches CLOSE_ENOUGH_AREA
        tracker = ScriptedTracker([_person(x=0.0, area=0.05)] * 100)
        ctrl = ApproachController(tracker, self._commands.append)
        ctrl.STEP_WAIT_S = 0.0
        ctrl.TIMEOUT_S = 0.05   # very short timeout
        result = ctrl.run()
        self.assertEqual(result, ApproachResult.TIMEOUT)


if __name__ == "__main__":
    unittest.main()
