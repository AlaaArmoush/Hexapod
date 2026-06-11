class BridgeError(Exception):
    pass


class NotConnectedError(BridgeError):
    pass


class ConnectionError(BridgeError):
    pass


class TimeoutError(BridgeError):
    pass


class AmbiguousCommandError(BridgeError):
    pass


class InvalidParameterError(BridgeError):
    pass


class FirmwareError(BridgeError):

    def __init__(self, error_code: str, raw: str):
        super().__init__(f"firmware error {error_code}: {raw}")
        self.error_code = error_code
        self.raw = raw
