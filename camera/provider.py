from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .config import (
    CAPTURE_FPS,
    CAPTURE_HEIGHT,
    CAPTURE_WIDTH,
    DEPTH_FPS,
    DEPTH_HEIGHT,
    DEPTH_WIDTH,
    DETECTION_CONFIDENCE_THRESHOLD,
    DETECTION_DEVICE_RETRIES,
    DETECTION_FPS,
    DETECTION_MAX_RESULTS,
    DETECTION_MODEL_YAML,
    DETECTION_RETRY_DELAY_S,
    ensure_capture_dir,
    sanitize_capture_label,
)
from .detection import (
    DetectionResult,
    detection_from_yolo_box,
    filter_detections,
    normalize_object_name,
)
from .depth import DepthProbeResult, summarize_center_depth
from .errors import (
    CameraCaptureError,
    CameraDependencyError,
    CameraDeviceNotFound,
    CameraDepthError,
    CameraDetectorError,
    CameraDetectorCrashed,
    CameraError,
    CameraPipelineError,
    CameraStereoUnavailable,
)
from .yolo_decode import decode_yolov6_outputs


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

    def depth_probe(self) -> DepthProbeResult:
        ...

    def detect_objects(self, target_label: str | None = None) -> DetectionResult:
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
        self._device = None
        self._pipeline = None
        self._color_queue = None
        self._depth_queue = None

    # ------------------------------------------------------------------
    # Persistent pipeline API (used by PersonTracker)
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Open the device and start a long-lived pipeline."""
        if self._pipeline is not None:
            return
        dai = self._import_depthai()
        device = self._open_device_with_retries(dai)
        pipeline = dai.Pipeline(device)

        color = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)
        color_out = color.requestOutput(
            (self.width, self.height),
            dai.ImgFrame.Type.BGR888i,
            fps=self.fps,
        )
        self._color_queue = color_out.createOutputQueue(maxSize=1, blocking=False)

        features = device.getConnectedCameraFeatures()
        has_stereo = (
            self._camera_feature(features, dai.CameraBoardSocket.CAM_B) is not None
            and self._camera_feature(features, dai.CameraBoardSocket.CAM_C) is not None
        )
        self._depth_queue = None
        if has_stereo:
            left = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_B)
            right = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_C)
            left_out = left.requestOutput((DEPTH_WIDTH, DEPTH_HEIGHT), dai.ImgFrame.Type.NV12, fps=DEPTH_FPS)
            right_out = right.requestOutput((DEPTH_WIDTH, DEPTH_HEIGHT), dai.ImgFrame.Type.NV12, fps=DEPTH_FPS)
            stereo = pipeline.create(dai.node.StereoDepth).build(
                left=left_out,
                right=right_out,
                presetMode=dai.node.StereoDepth.PresetMode.DEFAULT,
            )
            stereo.initialConfig.setMedianFilter(dai.MedianFilter.MEDIAN_OFF)
            stereo.setRectification(True)
            stereo.setExtendedDisparity(True)
            stereo.setLeftRightCheck(True)
            self._depth_queue = stereo.depth.createOutputQueue(maxSize=1, blocking=False)

        pipeline.start()
        self._device = device
        self._pipeline = pipeline

    def grab_frame(self):
        """Return latest BGR frame as numpy array, or None if not ready."""
        if self._color_queue is None:
            return None
        msg = self._color_queue.tryGet()
        return msg.getCvFrame() if msg is not None else None

    def grab_depth(self):
        """Return latest depth frame as numpy array, or None if unavailable."""
        if self._depth_queue is None:
            return None
        msg = self._depth_queue.tryGet()
        return msg.getFrame() if msg is not None else None

    def stop(self) -> None:
        """Tear down the persistent pipeline."""
        pipeline, self._pipeline = self._pipeline, None
        self._device = None
        self._color_queue = None
        self._depth_queue = None
        if pipeline is not None:
            try:
                pipeline.__exit__(None, None, None)
            except Exception:
                pass

    def status(self) -> CameraStatus:
        dai = self._import_depthai()

        try:
            device = self._open_device_with_retries(dai)
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

    def depth_probe(self) -> DepthProbeResult:
        dai = self._import_depthai()

        try:
            device = dai.Device()
            features = device.getConnectedCameraFeatures()
            if (
                self._camera_feature(features, dai.CameraBoardSocket.CAM_B) is None
                or self._camera_feature(features, dai.CameraBoardSocket.CAM_C) is None
            ):
                raise CameraStereoUnavailable("Stereo cameras CAM_B/C are not available.")

            with dai.Pipeline(device) as pipeline:
                left = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_B)
                right = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_C)
                left_out = left.requestOutput(
                    (DEPTH_WIDTH, DEPTH_HEIGHT),
                    dai.ImgFrame.Type.NV12,
                    fps=DEPTH_FPS,
                )
                right_out = right.requestOutput(
                    (DEPTH_WIDTH, DEPTH_HEIGHT),
                    dai.ImgFrame.Type.NV12,
                    fps=DEPTH_FPS,
                )
                stereo = pipeline.create(dai.node.StereoDepth).build(
                    left=left_out,
                    right=right_out,
                    presetMode=dai.node.StereoDepth.PresetMode.DEFAULT,
                )
                stereo.initialConfig.setMedianFilter(dai.MedianFilter.MEDIAN_OFF)
                stereo.setRectification(True)
                stereo.setExtendedDisparity(True)
                stereo.setLeftRightCheck(True)

                queue = stereo.depth.createOutputQueue(maxSize=1, blocking=True)
                pipeline.start()
                depth_msg = queue.get()
                captured_ms = int(time.time() * 1000)
                frame = depth_msg.getFrame()
                ended_ms = int(time.time() * 1000)
                return summarize_center_depth(frame, frame_age_ms=ended_ms - captured_ms)
        except CameraError:
            raise
        except Exception as exc:
            raise self._camera_exception(exc, depth=True) from exc

    def detect_objects(self, target_label: str | None = None) -> DetectionResult:
        dai = self._import_depthai()
        normalized_target = normalize_object_name(target_label) if target_label else None

        try:
            device = dai.Device()
            platform = device.getPlatform().name
            if platform != "RVC2":
                raise CameraDetectorError(f"Unsupported detector platform: {platform}")

            features = device.getConnectedCameraFeatures()
            if self._camera_feature(features, dai.CameraBoardSocket.CAM_A) is None:
                raise CameraDeviceNotFound("Color camera CAM_A is required for detections.")

            with dai.Pipeline(device) as pipeline:
                model_description = dai.NNModelDescription.fromYamlFile(str(DETECTION_MODEL_YAML))
                nn_archive = dai.NNArchive(dai.getModelFromZoo(model_description))
                classes = nn_archive.getConfig().model.heads[0].metadata.classes
                nn_size = nn_archive.getInputSize()

                color = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)
                color_out = color.requestOutput(nn_size, dai.ImgFrame.Type.BGR888p, fps=DETECTION_FPS)
                manip = pipeline.create(dai.node.ImageManip)
                manip.initialConfig.setOutputSize(*nn_size)
                manip.initialConfig.setFrameType(dai.ImgFrame.Type.BGR888p)
                manip.setMaxOutputFrameSize(nn_size[0] * nn_size[1] * 3)
                color_out.link(manip.inputImage)
                network = pipeline.create(dai.node.NeuralNetwork).build(manip.out, nn_archive)
                queue = network.out.createOutputQueue(maxSize=1, blocking=True)

                pipeline.start()
                nn_msg = queue.get()
                captured_ms = int(time.time() * 1000)
                tensors = [
                    nn_msg.getTensor(
                        tensor_name,
                        dequantize=True,
                        storageOrder=dai.TensorInfo.StorageOrder.NCHW,
                    )
                    for tensor_name in ["output1_yolov6r2", "output2_yolov6r2", "output3_yolov6r2"]
                ]
                decoded = decode_yolov6_outputs(
                    tensors,
                    confidence_threshold=DETECTION_CONFIDENCE_THRESHOLD,
                    iou_threshold=0.45,
                    num_classes=len(classes),
                )
                detections = []
                for box in decoded:
                    label_index = int(box[5])
                    if label_index < 0 or label_index >= len(classes):
                        continue
                    detections.append(detection_from_yolo_box(box, str(classes[label_index]), nn_size))

                filtered = filter_detections(
                    detections,
                    target_label=normalized_target,
                    confidence_threshold=DETECTION_CONFIDENCE_THRESHOLD,
                    max_results=DETECTION_MAX_RESULTS,
                )
                ended_ms = int(time.time() * 1000)
                return DetectionResult(
                    target_label=normalized_target,
                    detections=filtered,
                    frame_age_ms=max(0, ended_ms - captured_ms),
                )
        except CameraError:
            raise
        except Exception as exc:
            raise self._camera_exception(exc, detection=True) from exc

    def close(self) -> None:
        self.stop()

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
    def _open_device_with_retries(dai):
        last_exc = None
        for attempt in range(DETECTION_DEVICE_RETRIES):
            try:
                return dai.Device()
            except Exception as exc:
                last_exc = exc
                if attempt < DETECTION_DEVICE_RETRIES - 1:
                    time.sleep(DETECTION_RETRY_DELAY_S)
        raise last_exc

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
        depth: bool = False,
        detection: bool = False,
    ) -> CameraError:
        message = str(exc)
        if "No available devices" in message or "Device already closed" in message:
            return CameraDeviceNotFound(message)
        if detection and ("crashed" in message.lower() or "asset transfer" in message.lower()):
            return CameraDetectorCrashed(message)
        if detection:
            return CameraDetectorError(message)
        if depth:
            return CameraDepthError(message)
        if pipeline:
            return CameraPipelineError(message)
        if capture:
            return CameraCaptureError(message)
        return CameraError(message)
