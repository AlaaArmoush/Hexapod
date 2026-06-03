from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from .config import (
    DEPTH_CENTER_ROI_FRACTION,
    DEPTH_MAX_MM,
    DEPTH_MIN_MM,
)
from .errors import CameraDepthError


DepthRoiName = Literal["center"]


@dataclass(frozen=True)
class PixelRoi:
    name: DepthRoiName
    x_min: int
    y_min: int
    x_max: int
    y_max: int

    def as_dict(self) -> dict[str, int | str]:
        return {
            "name": self.name,
            "x_min": self.x_min,
            "y_min": self.y_min,
            "x_max": self.x_max,
            "y_max": self.y_max,
        }


@dataclass(frozen=True)
class DepthProbeResult:
    distance_m: float
    nearest_distance_m: float
    roi: str
    frame_age_ms: int
    depth_width: int
    depth_height: int
    valid_samples: int
    valid_ratio: float
    roi_pixels: dict[str, int | str]


def center_roi(width: int, height: int, fraction: float = DEPTH_CENTER_ROI_FRACTION) -> PixelRoi:
    if width <= 0 or height <= 0:
        raise CameraDepthError("invalid_depth_frame")
    if fraction <= 0 or fraction > 1:
        raise CameraDepthError("invalid_depth_roi")

    roi_width = max(1, int(width * fraction))
    roi_height = max(1, int(height * fraction))
    x_min = max(0, (width - roi_width) // 2)
    y_min = max(0, (height - roi_height) // 2)
    return PixelRoi(
        name="center",
        x_min=x_min,
        y_min=y_min,
        x_max=min(width, x_min + roi_width),
        y_max=min(height, y_min + roi_height),
    )


def summarize_center_depth(
    depth_frame_mm,
    *,
    frame_age_ms: int,
    min_mm: int = DEPTH_MIN_MM,
    max_mm: int = DEPTH_MAX_MM,
    roi_fraction: float = DEPTH_CENTER_ROI_FRACTION,
) -> DepthProbeResult:
    frame = np.asarray(depth_frame_mm)
    if frame.ndim != 2:
        raise CameraDepthError("invalid_depth_frame")

    height, width = frame.shape
    roi = center_roi(width, height, roi_fraction)
    roi_frame = frame[roi.y_min : roi.y_max, roi.x_min : roi.x_max]
    valid = roi_frame[(roi_frame >= min_mm) & (roi_frame <= max_mm)]
    valid = valid[np.isfinite(valid)]
    total_samples = int(roi_frame.size)
    if valid.size == 0:
        raise CameraDepthError(
            "depth_unavailable",
            data={
                "roi": roi.name,
                "depth_width": int(width),
                "depth_height": int(height),
                "roi_samples": total_samples,
                "valid_samples": 0,
                "valid_ratio": 0.0,
                "min_mm": int(min_mm),
                "max_mm": int(max_mm),
                "roi_pixels": roi.as_dict(),
            },
        )

    median_m = float(np.median(valid) / 1000.0)
    nearest_m = float(np.percentile(valid, 10) / 1000.0)
    return DepthProbeResult(
        distance_m=round(median_m, 3),
        nearest_distance_m=round(nearest_m, 3),
        roi=roi.name,
        frame_age_ms=max(0, int(frame_age_ms)),
        depth_width=int(width),
        depth_height=int(height),
        valid_samples=int(valid.size),
        valid_ratio=round(float(valid.size / total_samples), 3),
        roi_pixels=roi.as_dict(),
    )
