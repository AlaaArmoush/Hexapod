class CameraError(Exception):
    """Base exception for camera tool failures."""

    error_code = "camera_error"


class CameraConfigError(CameraError):
    error_code = "invalid_camera_config"


class CameraDependencyError(CameraError):
    error_code = "depthai_not_available"


class CameraDeviceNotFound(CameraError):
    error_code = "device_not_found"


class CameraPipelineError(CameraError):
    error_code = "pipeline_error"


class CameraCaptureError(CameraError):
    error_code = "capture_failed"
