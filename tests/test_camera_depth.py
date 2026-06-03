import unittest

import numpy as np

from camera.depth import center_roi, summarize_center_depth
from camera.errors import CameraDepthError


class CameraDepthTests(unittest.TestCase):
    def test_center_roi_uses_middle_fraction(self):
        roi = center_roi(100, 50, 0.2)

        self.assertEqual(roi.name, "center")
        self.assertEqual((roi.x_min, roi.y_min, roi.x_max, roi.y_max), (40, 20, 60, 30))

    def test_summarize_center_depth_filters_invalid_samples(self):
        frame = np.full((10, 10), 2000, dtype=np.uint16)
        frame[3:7, 3:7] = 1000
        frame[4, 4] = 0
        frame[5, 5] = 50000

        result = summarize_center_depth(frame, frame_age_ms=12, roi_fraction=0.4)

        self.assertEqual(result.distance_m, 1.0)
        self.assertEqual(result.nearest_distance_m, 1.0)
        self.assertEqual(result.roi, "center")
        self.assertEqual(result.frame_age_ms, 12)
        self.assertEqual(result.depth_width, 10)
        self.assertEqual(result.depth_height, 10)
        self.assertEqual(result.valid_samples, 14)
        self.assertEqual(result.valid_ratio, 0.875)

    def test_summarize_center_depth_rejects_frame_without_valid_depth(self):
        frame = np.zeros((10, 10), dtype=np.uint16)

        with self.assertRaises(CameraDepthError) as context:
            summarize_center_depth(frame, frame_age_ms=0)
        self.assertEqual(context.exception.data["valid_samples"], 0)
        self.assertEqual(context.exception.data["roi"], "center")

    def test_summarize_center_depth_rejects_non_2d_frame(self):
        frame = np.zeros((10, 10, 3), dtype=np.uint8)

        with self.assertRaises(CameraDepthError):
            summarize_center_depth(frame, frame_age_ms=0)


if __name__ == "__main__":
    unittest.main()
