import unittest

from camera.clearance import clearance_from_depth, validate_clearance_args
from camera.depth import DepthProbeResult
from camera.errors import CameraConfigError, CameraDepthError


def _depth_result(*, nearest_distance_m=0.8, frame_age_ms=20):
    return DepthProbeResult(
        distance_m=nearest_distance_m,
        nearest_distance_m=nearest_distance_m,
        roi="center",
        frame_age_ms=frame_age_ms,
        depth_width=320,
        depth_height=200,
        valid_samples=2400,
        valid_ratio=0.94,
        roi_pixels={"name": "center", "x_min": 128, "y_min": 80, "x_max": 192, "y_max": 120},
    )


class CameraClearanceTests(unittest.TestCase):
    def test_clearance_reports_clear_when_distance_exceeds_threshold(self):
        result = clearance_from_depth(_depth_result(nearest_distance_m=0.8), min_clear_m=0.5)

        self.assertTrue(result.clear)
        self.assertEqual(result.min_distance_m, 0.8)
        self.assertEqual(result.threshold_m, 0.5)
        self.assertEqual(result.roi, "center")

    def test_clearance_reports_blocked_when_distance_is_under_threshold(self):
        result = clearance_from_depth(_depth_result(nearest_distance_m=0.3), min_clear_m=0.5)

        self.assertFalse(result.clear)
        self.assertEqual(result.min_distance_m, 0.3)

    def test_clearance_rejects_stale_depth(self):
        with self.assertRaises(CameraDepthError) as context:
            clearance_from_depth(_depth_result(frame_age_ms=1500), min_clear_m=0.5)

        self.assertEqual(context.exception.data["frame_age_ms"], 1500)
        self.assertEqual(context.exception.data["max_frame_age_ms"], 1000)

    def test_validate_clearance_args_rejects_bad_roi(self):
        with self.assertRaises(CameraConfigError):
            validate_clearance_args(roi="wide")

    def test_validate_clearance_args_rejects_bad_threshold(self):
        for threshold in (True, "bad", 0.01, 10.0):
            with self.subTest(threshold=threshold):
                with self.assertRaises(CameraConfigError):
                    validate_clearance_args(min_clear_m=threshold)

    def test_validate_clearance_args_accepts_cli_numeric_string(self):
        threshold_m, roi = validate_clearance_args(min_clear_m="0.75", roi="center")

        self.assertEqual(threshold_m, 0.75)
        self.assertEqual(roi, "center")


if __name__ == "__main__":
    unittest.main()
