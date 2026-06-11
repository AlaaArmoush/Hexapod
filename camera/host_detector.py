from __future__ import annotations

import time
from pathlib import Path

import cv2
import numpy as np

from .config import DETECTION_CONFIDENCE_THRESHOLD, DETECTION_MAX_RESULTS
from .detection import (
    DetectionResult,
    ObjectDetection,
    detection_from_yolo_box,
    filter_detections,
    normalize_object_name,
)
from .errors import CameraDependencyError
from .yolo_decode import _nms


def _default_model() -> str:
    onnx = Path("yolov8n.onnx")
    return str(onnx) if onnx.exists() else "yolov8n.pt"


# YOLOv8 COCO class names in fixed index order (matches model output indices 0-79)
_COCO_NAMES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck",
    "boat", "traffic light", "fire hydrant", "stop sign", "parking meter", "bench",
    "bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra",
    "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee",
    "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove",
    "skateboard", "surfboard", "tennis racket", "bottle", "wine glass", "cup",
    "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
    "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch",
    "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse",
    "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear", "hair drier",
    "toothbrush",
]


class _OnnxBackend:
    """Pure onnxruntime inference — no torch, no ultralytics."""

    NN = 640

    def __init__(self, model_path: str) -> None:
        try:
            import onnxruntime as ort
        except ImportError as exc:
            raise CameraDependencyError("onnxruntime_not_available") from exc
        self._session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        self._input_name = self._session.get_inputs()[0].name

    def __call__(self, frame: np.ndarray):
        """Return list of [x1, y1, x2, y2, conf, class_id] in frame pixel coords."""
        h, w = frame.shape[:2]

        # Preprocess: BGR → RGB, resize to 640x640, NCHW float32 0-1
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (self.NN, self.NN))
        blob = resized.astype(np.float32) / 255.0
        blob = blob.transpose(2, 0, 1)[np.newaxis]  # [1, 3, 640, 640]

        raw = self._session.run(None, {self._input_name: blob})[0]  # [1, 84, 8400]
        preds = raw[0].T  # [8400, 84]

        boxes_cxcywh = preds[:, :4]            # normalised cx,cy,w,h (0-1 in 640 space)
        class_scores = preds[:, 4:]            # [8400, 80]
        class_ids = class_scores.argmax(axis=1)
        confidences = class_scores.max(axis=1)

        mask = confidences >= DETECTION_CONFIDENCE_THRESHOLD
        boxes_cxcywh = boxes_cxcywh[mask]
        confidences = confidences[mask]
        class_ids = class_ids[mask]

        if len(boxes_cxcywh) == 0:
            return []

        # Convert cx,cy,w,h (640-space) → x1,y1,x2,y2 in original frame pixels
        scale_x, scale_y = w / self.NN, h / self.NN
        cx = boxes_cxcywh[:, 0] * self.NN * scale_x
        cy = boxes_cxcywh[:, 1] * self.NN * scale_y
        bw = boxes_cxcywh[:, 2] * self.NN * scale_x
        bh = boxes_cxcywh[:, 3] * self.NN * scale_y
        x1, y1 = cx - bw / 2, cy - bh / 2
        x2, y2 = cx + bw / 2, cy + bh / 2

        dets = np.stack([x1, y1, x2, y2, confidences], axis=1).astype(np.float32)
        keep = _nms(dets, nms_thresh=0.45)

        return [
            [float(x1[i]), float(y1[i]), float(x2[i]), float(y2[i]),
             float(confidences[i]), int(class_ids[i])]
            for i in keep
        ]


class _UltralyticsBackend:
    """ultralytics backend — requires torch, works on x86 dev machine."""

    def __init__(self, model_path: str) -> None:
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise CameraDependencyError("ultralytics_not_available") from exc
        self._model = YOLO(model_path)

    def __call__(self, frame: np.ndarray):
        h, w = frame.shape[:2]
        results = self._model(frame, verbose=False, imgsz=640)[0]
        if results.boxes is None:
            return []
        return [
            [*box_xyxy, float(conf), int(cls_id)]
            for box_xyxy, conf, cls_id in zip(
                results.boxes.xyxy.tolist(),
                results.boxes.conf.tolist(),
                results.boxes.cls.tolist(),
            )
        ]


class HostDetector:
    """CPU-side YOLOv8n detector.

    On Pi:    copy yolov8n.onnx to repo root → uses pure onnxruntime (no torch).
    On laptop: uses ultralytics + torch via yolov8n.pt.
    """

    def __init__(self, model_name: str | None = None) -> None:
        if model_name is None:
            model_name = _default_model()
        if model_name.endswith(".onnx"):
            self._backend = _OnnxBackend(model_name)
            self._source = "yolov8n_onnx"
        else:
            self._backend = _UltralyticsBackend(model_name)
            self._source = "yolov8n_host"

    def detect(self, frame: np.ndarray, target_label: str | None = None) -> DetectionResult:
        normalized_target = normalize_object_name(target_label) if target_label else None
        frame_h, frame_w = frame.shape[:2]

        t0 = int(time.time() * 1000)
        raw_boxes = self._backend(frame)
        t1 = int(time.time() * 1000)

        detections: list[ObjectDetection] = []
        for box in raw_boxes:
            cls_id = int(box[5])
            label = _COCO_NAMES[cls_id] if cls_id < len(_COCO_NAMES) else str(cls_id)
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
            source=self._source,
        )
