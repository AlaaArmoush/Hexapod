import unittest

from camera.detection import (
    ObjectDetection,
    filter_detections,
    normalize_object_name,
)
from camera.errors import CameraConfigError


class CameraDetectionTests(unittest.TestCase):
    def test_normalize_object_name_accepts_supported_class_and_aliases(self):
        self.assertEqual(normalize_object_name("bottle"), "bottle")
        self.assertEqual(normalize_object_name(" mobile_phone "), "cell phone")
        self.assertEqual(normalize_object_name("sofa"), "couch")

    def test_normalize_object_name_rejects_unsupported_class(self):
        with self.assertRaises(CameraConfigError):
            normalize_object_name("hexapod")

    def test_filter_detections_filters_by_label_and_confidence(self):
        detections = [
            ObjectDetection(label="person", confidence=0.8, frame_position_x=0.0, frame_position_y=0.0),
            ObjectDetection(label="person", confidence=0.2, frame_position_x=0.0, frame_position_y=0.0),
            ObjectDetection(label="bottle", confidence=0.9, frame_position_x=0.0, frame_position_y=0.0),
        ]

        filtered = filter_detections(detections, target_label="person", confidence_threshold=0.45)

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].label, "person")
        self.assertEqual(filtered[0].confidence, 0.8)

    def test_filter_detections_sorts_by_confidence_and_limits_results(self):
        detections = [
            ObjectDetection(label="person", confidence=0.6, frame_position_x=0.0, frame_position_y=0.0),
            ObjectDetection(label="person", confidence=0.9, frame_position_x=0.0, frame_position_y=0.0),
        ]

        filtered = filter_detections(detections, confidence_threshold=0.45, max_results=1)

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].confidence, 0.9)


if __name__ == "__main__":
    unittest.main()
