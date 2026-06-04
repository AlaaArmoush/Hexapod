from __future__ import annotations

import os
import re
from pathlib import Path

from .errors import CameraConfigError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CAPTURE_DIR = PROJECT_ROOT / "data" / "captures"
CAPTURE_DIR = Path(os.environ.get("HEXAPOD_CAPTURE_DIR", DEFAULT_CAPTURE_DIR))
CAPTURE_WIDTH = 1920
CAPTURE_HEIGHT = 1080
CAPTURE_FPS = 5
DEPTH_WIDTH = 640
DEPTH_HEIGHT = 400
DEPTH_FPS = 5
DEPTH_CENTER_ROI_FRACTION = 0.2
DEPTH_MIN_MM = 200
DEPTH_MAX_MM = 30000
OBSTACLE_STOP_THRESHOLD_M = 0.5
CLEARANCE_MAX_FRAME_AGE_MS = 1000
DETECTION_FPS = 2
DETECTION_CONFIDENCE_THRESHOLD = 0.45
DETECTION_MAX_RESULTS = 10
DETECTION_DEVICE_RETRIES = 3
DETECTION_RETRY_DELAY_S = 2.0
DETECTION_MODEL_YAML = (
    PROJECT_ROOT
    / "oak-examples"
    / "neural-networks"
    / "object-detection"
    / "spatial-detections"
    / "depthai_models"
    / "yolov6_nano_r2_coco.RVC2.yaml"
)
MAX_LABEL_LENGTH = 48
_SAFE_LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,47}$")
_FORBIDDEN_LABEL_TOKENS = {"raw", "pixel", "pixels", "bitmap"}


def sanitize_capture_label(label: str | None) -> str | None:
    if label is None:
        return None
    if not isinstance(label, str):
        raise CameraConfigError("invalid_label")

    normalized = label.strip().replace(" ", "_")
    if not normalized:
        return None
    label_tokens = {token.lower() for token in re.split(r"[_-]+", normalized)}
    if (
        len(normalized) > MAX_LABEL_LENGTH
        or not _SAFE_LABEL_RE.fullmatch(normalized)
        or label_tokens & _FORBIDDEN_LABEL_TOKENS
    ):
        raise CameraConfigError("invalid_label")
    return normalized


def ensure_capture_dir(capture_dir: Path | None = None) -> Path:
    path = capture_dir or CAPTURE_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path
