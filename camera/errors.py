class CameraError(Exception):
    """Base exception for camera tool failures."""

    error_code = "camera_error"

    def __init__(self, message: str | None = None, *, data: dict | None = None) -> None:
        super().__init__(message or self.error_code)
        self.data = dict(data or {})


class CameraConfigError(CameraError):
    error_code = "invalid_camera_config"


class CameraUnsupportedObjectClass(CameraConfigError):
    error_code = "unsupported_object_class"


class CameraDependencyError(CameraError):
    error_code = "depthai_not_available"


class CameraDeviceNotFound(CameraError):
    error_code = "device_not_found"


class CameraPipelineError(CameraError):
    error_code = "pipeline_error"


class CameraCaptureError(CameraError):
    error_code = "capture_failed"


class CameraStereoUnavailable(CameraError):
    error_code = "stereo_not_available"


class CameraDepthError(CameraError):
    error_code = "depth_unavailable"


class CameraDetectorError(CameraError):
    error_code = "detector_unavailable"


class CameraDetectorCrashed(CameraDetectorError):
    error_code = "detector_crashed"
