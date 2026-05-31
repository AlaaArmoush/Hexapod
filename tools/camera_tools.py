from __future__ import annotations

from camera.errors import CameraConfigError, CameraError
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


def _camera_error(action: str, exc: CameraError, spoken_text: str) -> ToolResult:
    return ToolResult(
        ok=False,
        action=action,
        spoken_text=spoken_text,
        data={},
        display_face="camera",
        error=exc.error_code,
    )
