"""
Wake Word Pipeline — Phase 2 (Pi hardware).

Usage:
    python -m raspberry_pi.wake_word.pipeline

State machine: IDLE → LISTENING → WAKEWORD_DETECTED → PANNING → IDLE
"""
from __future__ import annotations

import sys
import time
from enum import Enum, auto
from pathlib import Path

from bridge.robot_commands import build_camera_pan
from .detector import WakeWordDetector

WAKEWORD_MODEL_PATH = Path(__file__).resolve().parents[2] / "hey_hek_sah.onnx"
WAKEWORD_THRESHOLD = 0.3
AUDIO_DEVICE = 1          # hexapod combined overlay capture (hw:0,1)
SERIAL_PORT = "/dev/ttyUSB0"
COOLDOWN_SECS = 2.0


class _State(Enum):
    IDLE = auto()
    LISTENING = auto()
    WAKEWORD_DETECTED = auto()
    PANNING = auto()


class WakeWordPipeline:
    def __init__(self) -> None:
        from bridge.serial_robot_bridge import SerialRobotBridge

        self._bridge = SerialRobotBridge(port=SERIAL_PORT)
        self._state = _State.IDLE
        self._detector: WakeWordDetector | None = None
        self._last_detection_time: float = 0.0

    def _on_wakeword(self, model_name: str, score: float, direction: str) -> None:
        if self._state != _State.LISTENING:
            return
        if time.monotonic() - self._last_detection_time < COOLDOWN_SECS:
            return
        self._last_detection_time = time.monotonic()
        print(f"\n[wake] '{model_name}' detected (score={score:.3f}, direction={direction!r})", file=sys.stderr)
        self._state = _State.WAKEWORD_DETECTED
        self._pan(direction)

    def _pan(self, direction: str) -> None:
        self._state = _State.PANNING
        pan_pos = direction if direction not in ("front", "back", "center") else "center"
        print(f"[pipeline] direction={direction!r} → camera_pan {pan_pos!r}", file=sys.stderr)
        self._bridge.send_command(build_camera_pan(pos=pan_pos))
        self._state = _State.LISTENING
        print("[pipeline] back to LISTENING", file=sys.stderr)

    def start(self) -> None:
        from raspberry_pi.audio.scripts.audio_mode import listen as audio_listen

        if not WAKEWORD_MODEL_PATH.exists():
            print(f"[pipeline] ERROR: model not found at {WAKEWORD_MODEL_PATH}", file=sys.stderr)
            sys.exit(1)

        print(f"[pipeline] connecting to ESP32 on {SERIAL_PORT}", file=sys.stderr)
        self._bridge.connect()

        print("[pipeline] setting audio mode: listen", file=sys.stderr)
        audio_listen()

        self._detector = WakeWordDetector(
            model_path=WAKEWORD_MODEL_PATH,
            on_wakeword=self._on_wakeword,
            threshold=WAKEWORD_THRESHOLD,
            device=AUDIO_DEVICE,
        )

        self._state = _State.LISTENING
        self._detector.start()
        print("[pipeline] LISTENING — say 'Hey Heksah'", file=sys.stderr)

        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n[pipeline] stopping", file=sys.stderr)
        finally:
            self.stop()

    def stop(self) -> None:
        from raspberry_pi.audio.scripts.audio_mode import off as audio_off

        if self._detector is not None:
            self._detector.stop()
            self._detector = None
        audio_off()
        self._bridge.close()
        self._state = _State.IDLE


def main() -> None:
    WakeWordPipeline().start()


if __name__ == "__main__":
    main()
