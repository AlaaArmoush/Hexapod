from __future__ import annotations

from dataclasses import dataclass

from .config import DETECTION_CONFIDENCE_THRESHOLD
from .errors import CameraUnsupportedObjectClass


COCO_CLASSES = {
    "person",
    "bicycle",
    "car",
    "motorcycle",
    "airplane",
    "bus",
    "train",
    "truck",
    "boat",
    "traffic light",
    "fire hydrant",
    "stop sign",
    "parking meter",
    "bench",
    "bird",
    "cat",
    "dog",
    "horse",
    "sheep",
    "cow",
    "elephant",
    "bear",
    "zebra",
    "giraffe",
    "backpack",
    "umbrella",
    "handbag",
    "tie",
    "suitcase",
    "frisbee",
    "skis",
    "snowboard",
    "sports ball",
    "kite",
    "baseball bat",
    "baseball glove",
    "skateboard",
    "surfboard",
    "tennis racket",
    "bottle",
    "wine glass",
    "cup",
    "fork",
    "knife",
    "spoon",
    "bowl",
    "banana",
    "apple",
    "sandwich",
    "orange",
    "broccoli",
    "carrot",
    "hot dog",
    "pizza",
    "donut",
    "cake",
    "chair",
    "couch",
    "potted plant",
    "bed",
    "dining table",
    "toilet",
    "tv",
    "laptop",
    "mouse",
    "remote",
    "keyboard",
    "cell phone",
    "microwave",
    "oven",
    "toaster",
    "sink",
    "refrigerator",
    "book",
    "clock",
    "vase",
    "scissors",
    "teddy bear",
    "hair drier",
    "toothbrush",
}

COCO_ALIASES = {
    "plant": "potted plant",
    "phone": "cell phone",
    "mobile phone": "cell phone",
    "cellphone": "cell phone",
    "sofa": "couch",
    "television": "tv",
}


@dataclass(frozen=True)
class ObjectDetection:
    label: str
    confidence: float
    frame_position_x: float
    frame_position_y: float
    distance_m: float | None = None

    def to_dict(self) -> dict:
        payload = {
            "label": self.label,
            "confidence": self.confidence,
            "frame_position_x": self.frame_position_x,
            "frame_position_y": self.frame_position_y,
        }
        if self.distance_m is not None:
            payload["distance_m"] = self.distance_m
        return payload


@dataclass(frozen=True)
class DetectionResult:
    target_label: str | None
    detections: list[ObjectDetection]
    frame_age_ms: int
    source: str = "yolov6_nano_r2_coco"

    @property
    def detected(self) -> bool:
        return bool(self.detections)

    @property
    def count(self) -> int:
        return len(self.detections)


def normalize_object_name(object_name: str) -> str:
    if not isinstance(object_name, str):
        raise CameraUnsupportedObjectClass("unsupported_object_class")

    normalized = " ".join(object_name.strip().lower().replace("_", " ").split())
    normalized = COCO_ALIASES.get(normalized, normalized)
    if normalized not in COCO_CLASSES:
        raise CameraUnsupportedObjectClass("unsupported_object_class")
    return normalized


def detection_from_depthai(raw_detection, label: str) -> ObjectDetection:
    center_x = (float(raw_detection.xmin) + float(raw_detection.xmax)) / 2.0
    center_y = (float(raw_detection.ymin) + float(raw_detection.ymax)) / 2.0
    distance_m = _distance_m(raw_detection)
    return ObjectDetection(
        label=label,
        confidence=round(float(raw_detection.confidence), 3),
        frame_position_x=round((center_x - 0.5) * 2.0, 3),
        frame_position_y=round((center_y - 0.5) * 2.0, 3),
        distance_m=distance_m,
    )


def detection_from_yolo_box(box, label: str, nn_size: tuple[int, int]) -> ObjectDetection:
    width, height = nn_size
    x_min, y_min, x_max, y_max, confidence, _class_id = box
    center_x = ((float(x_min) + float(x_max)) / 2.0) / width
    center_y = ((float(y_min) + float(y_max)) / 2.0) / height
    return ObjectDetection(
        label=label,
        confidence=round(float(confidence), 3),
        frame_position_x=round((center_x - 0.5) * 2.0, 3),
        frame_position_y=round((center_y - 0.5) * 2.0, 3),
        distance_m=None,
    )


def filter_detections(
    detections: list[ObjectDetection],
    *,
    target_label: str | None = None,
    confidence_threshold: float = DETECTION_CONFIDENCE_THRESHOLD,
    max_results: int | None = None,
) -> list[ObjectDetection]:
    filtered = [
        detection
        for detection in detections
        if detection.confidence >= confidence_threshold
        and (target_label is None or detection.label == target_label)
    ]
    filtered.sort(key=lambda item: item.confidence, reverse=True)
    if max_results is not None:
        return filtered[:max_results]
    return filtered


def _distance_m(raw_detection) -> float | None:
    spatial = getattr(raw_detection, "spatialCoordinates", None)
    if spatial is None:
        return None
    z_mm = getattr(spatial, "z", None)
    if z_mm is None or z_mm <= 0:
        return None
    return round(float(z_mm) / 1000.0, 3)
