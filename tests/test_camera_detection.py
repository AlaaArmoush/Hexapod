import unittest

from camera.detection import (
    ObjectDetection,
    detection_from_depthai,
    detection_from_yolo_box,
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

    def test_bbox_area_in_range_and_in_to_dict(self):
        det = ObjectDetection(
            label="person", confidence=0.9,
            frame_position_x=0.0, frame_position_y=0.0,
            bbox_area=0.25,
        )
        self.assertGreaterEqual(det.bbox_area, 0.0)
        self.assertLessEqual(det.bbox_area, 1.0)
        self.assertIn("bbox_area", det.to_dict())

    def test_detection_from_yolo_box_populates_bbox_area(self):
        # 640x640 frame, box occupies a quarter of the area
        box = [160.0, 160.0, 480.0, 480.0, 0.85, 0]
        det = detection_from_yolo_box(box, "person", (640, 640))
        self.assertGreater(det.bbox_area, 0.0)
        self.assertLessEqual(det.bbox_area, 1.0)
        self.assertAlmostEqual(det.bbox_area, 0.25, places=3)

    def test_detection_from_depthai_populates_bbox_area(self):
        class FakeSpatial:
            z = 1500.0

        class FakeDetection:
            xmin = 0.25
            xmax = 0.75
            ymin = 0.25
            ymax = 0.75
            confidence = 0.9
            spatialCoordinates = FakeSpatial()

        det = detection_from_depthai(FakeDetection(), "person")
        self.assertGreater(det.bbox_area, 0.0)
        self.assertLessEqual(det.bbox_area, 1.0)
        self.assertAlmostEqual(det.bbox_area, 0.25, places=3)

    def test_bbox_area_zero_default_for_manually_constructed_detection(self):
        det = ObjectDetection(label="bottle", confidence=0.7, frame_position_x=0.1, frame_position_y=-0.2)
        self.assertEqual(det.bbox_area, 0.0)
        self.assertIn("bbox_area", det.to_dict())


if __name__ == "__main__":
    unittest.main()
