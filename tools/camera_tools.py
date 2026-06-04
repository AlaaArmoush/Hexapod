from __future__ import annotations

from camera.errors import CameraConfigError, CameraError
from camera.clearance import clearance_from_depth
from camera.detection import normalize_object_name
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


def detect_person() -> ToolResult:
    return _detect_target("detect_person", "person")


def observe_scene() -> ToolResult:
    provider = DepthAICameraProvider()
    try:
        result = provider.detect_objects(target_label=None)
    except CameraError as exc:
        return _camera_error("observe_scene", exc, "Observation unavailable.")
    finally:
        provider.close()

    detections = [detection.to_dict() for detection in result.detections]
    if not detections:
        spoken_text = "I do not see any supported objects clearly."
    else:
        labels = []
        for detection in result.detections:
            if detection.label not in labels:
                labels.append(detection.label)
        if len(labels) == 1:
            spoken_text = f"I can see {labels[0]}."
        elif len(labels) == 2:
            spoken_text = f"I can see {labels[0]} and {labels[1]}."
        else:
            spoken_text = f"I can see {', '.join(labels[:3])}."

    return ToolResult(
        ok=True,
        action="observe_scene",
        spoken_text=spoken_text,
        data={
            "detected": bool(detections),
            "count": len(detections),
            "detections": detections,
            "frame_age_ms": result.frame_age_ms,
            "source": result.source,
        },
        display_face="camera",
    )


def detect_object(object_name: str) -> ToolResult:
    try:
        target = normalize_object_name(object_name)
    except CameraConfigError as exc:
        return ToolResult(
            ok=False,
            action="detect_object",
            spoken_text="That object class is not supported.",
            data={"object_name": object_name},
            display_face="camera",
            error=exc.error_code,
        )
    return _detect_target("detect_object", target, object_name=target)


def _detect_target(action: str, target_label: str, *, object_name: str | None = None) -> ToolResult:
    provider = DepthAICameraProvider()
    try:
        result = provider.detect_objects(target_label=target_label)
    except CameraConfigError as exc:
        return _camera_error(action, exc, "That object class is not supported.")
    except CameraError as exc:
        return _camera_error(action, exc, "Detection unavailable.")
    finally:
        provider.close()

    detections = [detection.to_dict() for detection in result.detections]
    data = {
        "detected": result.detected,
        "count": result.count,
        "detections": detections,
        "frame_age_ms": result.frame_age_ms,
        "source": result.source,
    }
    if object_name is not None:
        data["object_name"] = object_name

    if not result.detected:
        spoken_text = (
            "No person visible."
            if target_label == "person"
            else f"No {target_label} visible."
        )
    else:
        first = result.detections[0]
        if first.distance_m is None:
            distance_text = ""
        else:
            distance_text = f" about {first.distance_m:.1f} metres away"
        if result.count == 1:
            spoken_text = f"I can see one {target_label}{distance_text}."
        else:
            spoken_text = f"I can see {result.count} {target_label}s{distance_text}."

    return ToolResult(
        ok=True,
        action=action,
        spoken_text=spoken_text,
        data=data,
        display_face="camera",
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
