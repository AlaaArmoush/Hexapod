import unittest

import numpy as np

from camera.detection import DetectionResult, ObjectDetection
from camera.search import ObjectSearcher, SearchResult, _CAMERA_POSITIONS


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
    def __init__(self, detections: list):
        # detections[i] is returned for the i-th detect() call
        self._detections = detections
        self._call_count = 0

    def detect(self, frame, target_label=None):
        idx = self._call_count
        self._call_count += 1
        dets = self._detections[idx] if idx < len(self._detections) else []
        return DetectionResult(target_label=target_label, detections=dets, frame_age_ms=10)


def _searcher(detections, commands):
    s = ObjectSearcher(FakeProvider(), FakeDetector(detections), commands.append)
    s.SETTLE_S = 0.0
    s.ROTATE_WAIT_S = 0.0
    return s


class SearchTests(unittest.TestCase):
    def setUp(self):
        self._commands = []

    def test_scans_camera_positions_at_each_body_orientation(self):
        s = _searcher([], self._commands)
        s.search("bottle")
        pan_cmds = [c["pos"] for c in self._commands if c.get("cmd") == "camera_pan"]
        # Each body orientation scans _CAMERA_POSITIONS
        self.assertEqual(pan_cmds[:len(_CAMERA_POSITIONS)], _CAMERA_POSITIONS)

    def test_rotates_body_between_scans(self):
        s = _searcher([], self._commands)
        s.search("bottle")
        rotate_cmds = [c for c in self._commands if c.get("cmd") == "rotate"]
        self.assertGreater(len(rotate_cmds), 0)

    def test_returns_not_found_when_no_detections(self):
        result = _searcher([], self._commands).search("bottle")
        self.assertFalse(result.found)
        self.assertIsNone(result.position)

    def test_returns_found_when_detection_present(self):
        # First orientation, first camera position gets a hit
        dets = [[_det("bottle", 0.8)]] + [[] for _ in range(20)]
        result = _searcher(dets, self._commands).search("bottle")
        self.assertTrue(result.found)
        self.assertIsNotNone(result.position)
        self.assertAlmostEqual(result.confidence, 0.8)

    def test_returns_distance_when_available(self):
        dets = [[_det("bottle", 0.8, dist=1.5)]] + [[] for _ in range(20)]
        result = _searcher(dets, self._commands).search("bottle")
        self.assertEqual(result.distance_m, 1.5)

    def test_returns_none_distance_when_unavailable(self):
        dets = [[_det("bottle", 0.8)]] + [[] for _ in range(20)]
        result = _searcher(dets, self._commands).search("bottle")
        self.assertIsNone(result.distance_m)

    def test_stops_early_on_confident_detection(self):
        # High-confidence hit on first camera position of first body orientation
        dets = [[_det("bottle", 0.9)]] + [[] for _ in range(20)]
        s = _searcher(dets, self._commands)
        s.search("bottle")
        rotate_cmds = [c for c in self._commands if c.get("cmd") == "rotate" and c.get("dir") == "left"]
        # Should stop early — fewer than 5 left-rotations (full 360°)
        self.assertLess(len(rotate_cmds), 5)


if __name__ == "__main__":
    unittest.main()
