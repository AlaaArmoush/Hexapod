from __future__ import annotations

import time

import numpy as np

from .detection import (
    DetectionResult,
    ObjectDetection,
    detection_from_yolo_box,
    filter_detections,
    normalize_object_name,
)
from .config import DETECTION_CONFIDENCE_THRESHOLD, DETECTION_MAX_RESULTS
from .errors import CameraDependencyError


class HostDetector:
    """CPU-side YOLOv8n fallback when OAK-D on-device model is unavailable."""

    NN_SIZE = (640, 640)

    def __init__(self, model_name: str = "yolov8n.pt") -> None:
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise CameraDependencyError("ultralytics_not_available") from exc
        self._model = YOLO(model_name)

    def detect(self, frame: np.ndarray, target_label: str | None = None) -> DetectionResult:
        """Run detection on a BGR frame. Returns filtered DetectionResult."""
        normalized_target = normalize_object_name(target_label) if target_label else None
        frame_h, frame_w = frame.shape[:2]

        t0 = int(time.time() * 1000)
        results = self._model(frame, verbose=False, imgsz=self.NN_SIZE[0])[0]
        t1 = int(time.time() * 1000)

        detections: list[ObjectDetection] = []
        if results.boxes is not None:
            names = results.names
            for box_xyxy, conf, cls_id in zip(
                results.boxes.xyxy.tolist(),
                results.boxes.conf.tolist(),
                results.boxes.cls.tolist(),
            ):
                label = names[int(cls_id)]
                # ultralytics returns coords in original frame space, not NN_SIZE
                box = [*box_xyxy, conf, cls_id]
                detections.append(detection_from_yolo_box(box, label, (frame_w, frame_h)))

        filtered = filter_detections(
            detections,
            target_label=normalized_target,
            confidence_threshold=DETECTION_CONFIDENCE_THRESHOLD,
            max_results=DETECTION_MAX_RESULTS,
        )
        return DetectionResult(
            target_label=normalized_target,
            detections=filtered,
            frame_age_ms=max(0, t1 - t0),
            source="yolov8n_host",
        )
