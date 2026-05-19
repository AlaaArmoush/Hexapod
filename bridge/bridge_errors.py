class BridgeError(Exception):
    """Base class for all SerialRobotBridge errors."""


class NotConnectedError(BridgeError):
    """send_command called before connect()."""


class ConnectionError(BridgeError):
    """Failed to open or lost the serial port."""


class TimeoutError(BridgeError):
    """wait_for_ok / wait_for_ready timed out."""


class AmbiguousCommandError(BridgeError):
    """Mutually exclusive command parameters were provided together."""


class InvalidParameterError(BridgeError):
    """A parameter value is outside the allowed range or type."""


class FirmwareError(BridgeError):
    """ESP32 returned ok=false."""

    def __init__(self, error_code: str, raw: str):
        super().__init__(f"firmware error {error_code}: {raw}")
        self.error_code = error_code
        self.raw = raw
