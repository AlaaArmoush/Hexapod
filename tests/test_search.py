import unittest

import numpy as np

from camera.detection import DetectionResult, ObjectDetection
from camera.search import ObjectSearcher, SearchResult


def _det(label, conf, dist=None):
    return ObjectDetection(
        label=label, confidence=conf,
        frame_position_x=0.0, frame_position_y=0.0,
        bbox_area=0.1, distance_m=dist,
    )


BLANK = np.zeros((480, 640, 3), dtype=np.uint8)


class FakeProvider:
    def grab_frame(self):
        return BLANK


class FakeDetector:
    def __init__(self, results_by_pos: dict):
        self._results = results_by_pos
        self._call_count = 0

    def detect(self, frame, target_label=None):
        idx = self._call_count
        self._call_count += 1
        positions = ["left", "front_left", "center", "front_right", "right"]
        pos = positions[idx] if idx < len(positions) else "center"
        dets = self._results.get(pos, [])
        return DetectionResult(target_label=target_label, detections=dets, frame_age_ms=10)


class SearchTests(unittest.TestCase):
    def setUp(self):
        self._commands = []

    def _searcher(self, results_by_pos):
        return ObjectSearcher(
            FakeProvider(),
            FakeDetector(results_by_pos),
            self._commands.append,
        )

    def _searcher_no_settle(self, results_by_pos):
        s = self._searcher(results_by_pos)
        s.SETTLE_S = 0.0
        return s

    def test_scans_all_positions(self):
        s = self._searcher_no_settle({})
        s.search("bottle")
        pan_cmds = [c for c in self._commands if c.get("cmd") == "camera_pan"]
        panned_positions = [c["pos"] for c in pan_cmds]
        self.assertEqual(panned_positions, ["left", "front_left", "center", "front_right", "right"])

    def test_always_returns_to_center(self):
        s = self._searcher_no_settle({})
        s.search("bottle")
        last = self._commands[-1]
        self.assertEqual(last["cmd"], "camera_center")

    def test_returns_not_found_when_no_detections(self):
        result = self._searcher_no_settle({}).search("bottle")
        self.assertFalse(result.found)
        self.assertIsNone(result.position)

    def test_returns_best_match_by_confidence(self):
        results = {
            "left":       [_det("bottle", 0.5)],
            "front_right":[_det("bottle", 0.9)],
        }
        result = self._searcher_no_settle(results).search("bottle")
        self.assertTrue(result.found)
        self.assertEqual(result.position, "front_right")
        self.assertAlmostEqual(result.confidence, 0.9)

    def test_returns_distance_when_available(self):
        results = {"center": [_det("bottle", 0.8, dist=1.5)]}
        result = self._searcher_no_settle(results).search("bottle")
        self.assertEqual(result.distance_m, 1.5)

    def test_returns_none_distance_when_unavailable(self):
        results = {"center": [_det("bottle", 0.8)]}
        result = self._searcher_no_settle(results).search("bottle")
        self.assertIsNone(result.distance_m)


if __name__ == "__main__":
    unittest.main()
