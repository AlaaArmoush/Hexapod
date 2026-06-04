from __future__ import annotations

from dataclasses import dataclass

from .config import CLEARANCE_MAX_FRAME_AGE_MS, OBSTACLE_STOP_THRESHOLD_M
from .depth import DepthProbeResult
from .errors import CameraConfigError, CameraDepthError


SUPPORTED_CLEARANCE_ROIS = {"center"}
MIN_CLEARANCE_THRESHOLD_M = 0.1
MAX_CLEARANCE_THRESHOLD_M = 5.0


@dataclass(frozen=True)
class ClearanceResult:
    clear: bool
    min_distance_m: float
    threshold_m: float
    roi: str
    frame_age_ms: int
    valid_ratio: float
    depth_width: int
    depth_height: int


def validate_clearance_args(
    *,
    min_clear_m: float | int | None = None,
    roi: str = "center",
) -> tuple[float, str]:
    if roi not in SUPPORTED_CLEARANCE_ROIS:
        raise CameraConfigError("invalid_clearance_roi")

    if min_clear_m is None:
        threshold_m = OBSTACLE_STOP_THRESHOLD_M
    elif isinstance(min_clear_m, bool):
        raise CameraConfigError("invalid_clearance_threshold")
    elif isinstance(min_clear_m, str):
        try:
            threshold_m = float(min_clear_m)
        except ValueError as exc:
            raise CameraConfigError("invalid_clearance_threshold") from exc
    elif not isinstance(min_clear_m, (int, float)):
        raise CameraConfigError("invalid_clearance_threshold")
    else:
        threshold_m = float(min_clear_m)

    if threshold_m < MIN_CLEARANCE_THRESHOLD_M or threshold_m > MAX_CLEARANCE_THRESHOLD_M:
        raise CameraConfigError("invalid_clearance_threshold")

    return threshold_m, roi


def clearance_from_depth(
    depth: DepthProbeResult,
    *,
    min_clear_m: float | int | None = None,
    roi: str = "center",
    max_frame_age_ms: int = CLEARANCE_MAX_FRAME_AGE_MS,
) -> ClearanceResult:
    threshold_m, roi = validate_clearance_args(min_clear_m=min_clear_m, roi=roi)

    if depth.roi != roi:
        raise CameraConfigError("invalid_clearance_roi")
    if depth.frame_age_ms > max_frame_age_ms:
        raise CameraDepthError(
            "frame_too_stale",
            data={
                "frame_age_ms": depth.frame_age_ms,
                "max_frame_age_ms": max_frame_age_ms,
                "roi": roi,
            },
        )

    min_distance_m = depth.nearest_distance_m
    return ClearanceResult(
        clear=min_distance_m >= threshold_m,
        min_distance_m=min_distance_m,
        threshold_m=threshold_m,
        roi=roi,
        frame_age_ms=depth.frame_age_ms,
        valid_ratio=depth.valid_ratio,
        depth_width=depth.depth_width,
        depth_height=depth.depth_height,
    )
