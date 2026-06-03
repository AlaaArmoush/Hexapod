from __future__ import annotations

from camera.errors import CameraConfigError, CameraError
from camera.clearance import clearance_from_depth
from camera.provider import DepthAICameraProvider

from .base import ToolResult


def camera_status() -> ToolResult:
    provider = DepthAICameraProvider()
    try:
        status = provider.status()
    except CameraError as exc:
        return _camera_error("camera_status", exc, "Camera is not connected.")
    finally:
        provider.close()

    return ToolResult(
        ok=True,
        action="camera_status",
        spoken_text="Camera is connected and running.",
        data={
            "connected": status.connected,
            "pipeline_running": status.pipeline_running,
            "device_id": status.device_id,
            "color_resolution": status.color_resolution,
            "stereo_available": status.stereo_available,
            "fps_color": status.fps_color,
        },
        display_face="camera",
    )


def capture_image(label: str | None = None) -> ToolResult:
    provider = DepthAICameraProvider()
    try:
        capture = provider.capture_image(label=label)
    except CameraConfigError as exc:
        return _camera_error("capture_image", exc, "That image label is not safe.")
    except CameraError as exc:
        return _camera_error("capture_image", exc, "Could not capture image.")
    finally:
        provider.close()

    return ToolResult(
        ok=True,
        action="capture_image",
        spoken_text="Image captured.",
        data={
            "path": capture.path,
            "timestamp_ms": capture.timestamp_ms,
            "width": capture.width,
            "height": capture.height,
            "age_ms": capture.age_ms,
        },
        display_face="camera",
    )


def depth_probe() -> ToolResult:
    provider = DepthAICameraProvider()
    try:
        depth = provider.depth_probe()
    except CameraError as exc:
        return _camera_error("depth_probe", exc, "Depth sensor unavailable.")
    finally:
        provider.close()

    return ToolResult(
        ok=True,
        action="depth_probe",
        spoken_text=f"Center depth is about {depth.distance_m:.2f} metres.",
        data={
            "distance_m": depth.distance_m,
            "nearest_distance_m": depth.nearest_distance_m,
            "roi": depth.roi,
            "frame_age_ms": depth.frame_age_ms,
            "depth_width": depth.depth_width,
            "depth_height": depth.depth_height,
            "valid_samples": depth.valid_samples,
            "valid_ratio": depth.valid_ratio,
            "roi_pixels": depth.roi_pixels,
        },
        display_face="camera",
    )


def check_clearance(min_clear_m: float | int | None = None, roi: str = "center") -> ToolResult:
    provider = DepthAICameraProvider()
    try:
        depth = provider.depth_probe()
        clearance = clearance_from_depth(depth, min_clear_m=min_clear_m, roi=roi)
    except CameraConfigError as exc:
        return _camera_error("check_clearance", exc, "That clearance request is not valid.")
    except CameraError as exc:
        return _camera_error("check_clearance", exc, "Depth sensor unavailable.")
    finally:
        provider.close()

    if clearance.clear:
        spoken_text = f"Path is clear. Closest center obstacle is {clearance.min_distance_m:.2f} metres away."
        display_face = "camera"
    else:
        spoken_text = f"Path is blocked. Closest center obstacle is {clearance.min_distance_m:.2f} metres away."
        display_face = "alert"

    return ToolResult(
        ok=True,
        action="check_clearance",
        spoken_text=spoken_text,
        data={
            "clear": clearance.clear,
            "min_distance_m": clearance.min_distance_m,
            "threshold_m": clearance.threshold_m,
            "roi": clearance.roi,
            "frame_age_ms": clearance.frame_age_ms,
            "valid_ratio": clearance.valid_ratio,
            "depth_width": clearance.depth_width,
            "depth_height": clearance.depth_height,
        },
        display_face=display_face,
    )


def _camera_error(action: str, exc: CameraError, spoken_text: str) -> ToolResult:
    return ToolResult(
        ok=False,
        action=action,
        spoken_text=spoken_text,
        data=dict(getattr(exc, "data", {}) or {}),
        display_face="camera",
        error=exc.error_code,
    )
