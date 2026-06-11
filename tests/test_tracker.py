import time
import unittest

import numpy as np

from camera.detection import DetectionResult, ObjectDetection
from camera.tracker import PersonTracker, TrackedPerson


def _det(label, conf, x, y, area=0.1, dist=None):
    return ObjectDetection(
        label=label, confidence=conf,
        frame_position_x=x, frame_position_y=y,
        bbox_area=area, distance_m=dist,
    )


def _result(*detections):
    return DetectionResult(target_label="person", detections=list(detections), frame_age_ms=10)


class FakeProvider:
    def __init__(self, frames):
        self._frames = iter(frames)
        self._done = False

    def grab_frame(self):
        try:
            return next(self._frames)
        except StopIteration:
            self._done = True
            return None


class FakeDetector:
    def __init__(self, results):
        self._results = iter(results)

    def detect(self, frame, target_label=None):
        try:
            return next(self._results)
        except StopIteration:
            return DetectionResult(target_label=target_label, detections=[], frame_age_ms=0)


BLANK = np.zeros((480, 640, 3), dtype=np.uint8)


class TrackerTests(unittest.TestCase):
    def _make_tracker(self, frames, results, fps=50):
        provider = FakeProvider(frames)
        detector = FakeDetector(results)
        return PersonTracker(provider, detector, fps=fps)

    def test_target_is_none_before_any_detection(self):
        tracker = self._make_tracker([BLANK], [_result()])
        self.assertIsNone(tracker.target)

    def test_detection_populates_target(self):
        tracker = self._make_tracker(
            [BLANK, BLANK],
            [_result(_det("person", 0.9, 0.5, 0.3, area=0.2))],
        )
        tracker.start()
        time.sleep(0.1)
        tracker.stop()
        t = tracker.target
        self.assertIsNotNone(t)
        self.assertIsInstance(t, TrackedPerson)
        self.assertAlmostEqual(t.frame_position_x, 0.5, places=2)

    def test_ema_smoothing_applied_on_second_detection(self):
        det1 = _det("person", 0.9, 0.0, 0.0, area=0.2)
        det2 = _det("person", 0.9, 1.0, 0.0, area=0.2)
        tracker = self._make_tracker(
            [BLANK, BLANK, BLANK],
            [_result(det1), _result(det2)],
            fps=100,
        )
        tracker.start()
        time.sleep(0.1)
        tracker.stop()
        t = tracker.target
        self.assertIsNotNone(t)
        # EMA alpha=0.4: after 2 ticks, x should be between 0.0 and 1.0
        self.assertGreater(t.frame_position_x, 0.0)
        self.assertLess(t.frame_position_x, 1.0)

    def test_pick_closest_prefers_distance_m_over_bbox_area(self):
        near = _det("person", 0.9, 0.0, 0.0, area=0.05, dist=0.8)  # close by depth, small bbox
        far  = _det("person", 0.9, 0.5, 0.0, area=0.9, dist=3.0)   # far by depth, huge bbox
        best = PersonTracker._pick_closest([near, far])
        self.assertEqual(best.distance_m, 0.8)

    def test_pick_closest_falls_back_to_bbox_area_when_no_depth(self):
        small = _det("person", 0.9, 0.0, 0.0, area=0.05)
        large = _det("person", 0.9, 0.5, 0.0, area=0.4)
        best = PersonTracker._pick_closest([small, large])
        self.assertAlmostEqual(best.bbox_area, 0.4)

    def test_lost_timeout_clears_target(self):
        tracker = self._make_tracker(
            [BLANK, BLANK],
            [_result(_det("person", 0.9, 0.0, 0.0, area=0.2))],
            fps=100,
        )
        tracker.LOST_TIMEOUT_MS = 50  # short for test
        tracker.start()
        time.sleep(0.05)   # let first detection land
        time.sleep(0.15)   # outlast the timeout with no new detections
        tracker.stop()
        self.assertIsNone(tracker.target)


if __name__ == "__main__":
    unittest.main()
