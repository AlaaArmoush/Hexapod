from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .config import (
    CAPTURE_FPS,
    CAPTURE_HEIGHT,
    CAPTURE_WIDTH,
    ensure_capture_dir,
    sanitize_capture_label,
)
from .errors import (
    CameraCaptureError,
    CameraDependencyError,
    CameraDeviceNotFound,
    CameraError,
    CameraPipelineError,
)


@dataclass(frozen=True)
class CameraStatus:
    connected: bool
    pipeline_running: bool
    device_id: str | None = None
    color_resolution: str | None = None
    stereo_available: bool = False
    fps_color: float | None = None


@dataclass(frozen=True)
class CaptureResult:
    path: str
    timestamp_ms: int
    width: int
    height: int
    age_ms: int


class CameraProvider(Protocol):
    def status(self) -> CameraStatus:
        ...

    def capture_image(self, label: str | None = None) -> CaptureResult:
        ...

    def close(self) -> None:
        ...


class DepthAICameraProvider:
    def __init__(
        self,
        *,
        capture_dir: Path | None = None,
        width: int = CAPTURE_WIDTH,
        height: int = CAPTURE_HEIGHT,
        fps: int = CAPTURE_FPS,
    ) -> None:
        self.capture_dir = capture_dir
        self.width = width
        self.height = height
        self.fps = fps

    def status(self) -> CameraStatus:
        dai = self._import_depthai()

        try:
            device = dai.Device()
            with dai.Pipeline(device) as pipeline:
                color = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)
                color_out = color.requestOutput(
                    (self.width, self.height),
                    dai.ImgFrame.Type.NV12,
                    fps=self.fps,
                )
                color_out.createOutputQueue(maxSize=1, blocking=False)
                pipeline.start()
                features = device.getConnectedCameraFeatures()
                color_feature = self._camera_feature(features, dai.CameraBoardSocket.CAM_A)
                stereo_available = (
                    self._camera_feature(features, dai.CameraBoardSocket.CAM_B) is not None
                    and self._camera_feature(features, dai.CameraBoardSocket.CAM_C) is not None
                )
                return CameraStatus(
                    connected=True,
                    pipeline_running=bool(pipeline.isRunning()),
                    device_id=self._device_id(device.getDeviceInfo()),
                    color_resolution=self._resolution_label(color_feature),
                    stereo_available=stereo_available,
                    fps_color=float(self.fps),
                )
        except CameraError:
            raise
        except Exception as exc:
            raise self._camera_exception(exc, pipeline=True) from exc

    def capture_image(self, label: str | None = None) -> CaptureResult:
        dai = self._import_depthai()
        safe_label = sanitize_capture_label(label)
        capture_dir = ensure_capture_dir(self.capture_dir)

        try:
            import cv2
        except ImportError as exc:
            raise CameraDependencyError("opencv_not_available") from exc

        try:
            device = dai.Device()
            with dai.Pipeline(device) as pipeline:
                color = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)
                color_out = color.requestOutput(
                    (self.width, self.height),
                    dai.ImgFrame.Type.BGR888i,
                    fps=self.fps,
                )
                queue = color_out.createOutputQueue(maxSize=1, blocking=True)
                pipeline.start()
                frame_msg = queue.get()
                captured_ms = int(time.time() * 1000)
                frame = frame_msg.getCvFrame()
                filename = self._capture_filename(captured_ms, safe_label)
                path = capture_dir / filename
                ok = cv2.imwrite(str(path), frame)
                if not ok:
                    raise CameraCaptureError("Could not write image.")
                ended_ms = int(time.time() * 1000)
                return CaptureResult(
                    path=str(path),
                    timestamp_ms=captured_ms,
                    width=int(frame.shape[1]),
                    height=int(frame.shape[0]),
                    age_ms=max(0, ended_ms - captured_ms),
                )
        except CameraError:
            raise
        except Exception as exc:
            raise self._camera_exception(exc, capture=True) from exc

    def close(self) -> None:
        return None

    @staticmethod
    def _import_depthai():
        try:
            import depthai as dai
        except ImportError as exc:
            raise CameraDependencyError("depthai_not_available") from exc
        return dai

    @staticmethod
    def _camera_feature(features, socket):
        for feature in features:
            if feature.socket == socket:
                return feature
        return None

    @staticmethod
    def _resolution_label(feature) -> str | None:
        if feature is None:
            return None
        if feature.width >= 1920 and feature.height >= 1080:
            return "1080p"
        return f"{feature.width}x{feature.height}"

    @staticmethod
    def _device_id(device_info) -> str:
        if hasattr(device_info, "getDeviceId"):
            return str(device_info.getDeviceId())
        if hasattr(device_info, "deviceId"):
            return str(device_info.deviceId)
        return str(device_info)

    @staticmethod
    def _capture_filename(timestamp_ms: int, label: str | None) -> str:
        stamp = time.strftime("%Y%m%d_%H%M%S", time.localtime(timestamp_ms / 1000))
        suffix = f"_{label}" if label else ""
        return f"hexapod{suffix}_{stamp}_{timestamp_ms % 1000:03d}.jpg"

    @staticmethod
    def _camera_exception(
        exc: Exception,
        *,
        pipeline: bool = False,
        capture: bool = False,
    ) -> CameraError:
        message = str(exc)
        if "No available devices" in message or "Device already closed" in message:
            return CameraDeviceNotFound(message)
        if pipeline:
            return CameraPipelineError(message)
        if capture:
            return CameraCaptureError(message)
        return CameraError(message)
