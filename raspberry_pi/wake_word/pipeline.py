"""
Wake Word Pipeline — Phase 1 (laptop mock).

Usage:
    python -m raspberry_pi.wake_word.pipeline --mock
    python -m raspberry_pi.wake_word.pipeline          # real direction (Pi only)

State machine: IDLE → LISTENING → WAKEWORD_DETECTED → PANNING → IDLE
"""
from __future__ import annotations

import argparse
import sys
import time
from enum import Enum, auto
from pathlib import Path

import numpy as np

from .detector import WakeWordDetector
from .direction import DirectionEstimator, make_direction_estimator
from .servo_response import respond_to_direction

WAKEWORD_MODEL_PATH = Path(__file__).resolve().parents[2] / "hey_hek_sah.onnx"
WAKEWORD_THRESHOLD = 0.3
DIRECTION_HISTORY = 5
AUDIO_DEVICE = None       # None = system default; set to int on Pi
COOLDOWN_SECS = 2.0       # suppress re-triggers while the utterance is still ringing


class _State(Enum):
    IDLE = auto()
    LISTENING = auto()
    WAKEWORD_DETECTED = auto()
    PANNING = auto()


class WakeWordPipeline:
    def __init__(self, use_mock: bool = False, bridge: object | None = None) -> None:
        self._use_mock = use_mock
        self._bridge = bridge
        self._state = _State.IDLE
        self._direction_est: DirectionEstimator = make_direction_estimator(use_mock=use_mock)
        self._pending_direction: str = "center"
        self._detector: WakeWordDetector | None = None
        self._last_detection_time: float = 0.0

    def _on_wakeword(self, model_name: str, score: float) -> None:
        if self._state != _State.LISTENING:
            return
        if time.monotonic() - self._last_detection_time < COOLDOWN_SECS:
            return
        self._last_detection_time = time.monotonic()
        print(f"\n[wake] '{model_name}' detected (score={score:.3f})", file=sys.stderr)
        self._state = _State.WAKEWORD_DETECTED
        self._pending_direction = self._direction_est.estimate(np.array([], dtype=np.int16))
        self._pan()

    def _pan(self) -> None:
        self._state = _State.PANNING
        print(f"[pipeline] direction={self._pending_direction!r} → sending camera_pan", file=sys.stderr)
        respond_to_direction(self._pending_direction, self._bridge)
        self._direction_est.reset()
        self._state = _State.LISTENING
        print("[pipeline] back to LISTENING", file=sys.stderr)

    def on_wakeword_confirmed(self, direction: str) -> None:
        """Entry point for future STT stage."""
        pass

    def start(self) -> None:
        if not WAKEWORD_MODEL_PATH.exists():
            print(f"[pipeline] ERROR: model not found at {WAKEWORD_MODEL_PATH}", file=sys.stderr)
            sys.exit(1)

        print(f"[pipeline] starting (mock={self._use_mock})", file=sys.stderr)
        print(f"[pipeline] model: {WAKEWORD_MODEL_PATH}", file=sys.stderr)
        print(f"[pipeline] threshold: {WAKEWORD_THRESHOLD}", file=sys.stderr)

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
        if self._detector is not None:
            self._detector.stop()
            self._detector = None
        self._state = _State.IDLE


def main() -> None:
    parser = argparse.ArgumentParser(description="Wake word → camera pan pipeline")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="[MOCK — DELETE BEFORE PI] Use mock direction estimator (cycles left/center/right)",
    )
    args = parser.parse_args()

    pipeline = WakeWordPipeline(use_mock=args.mock)
    pipeline.start()


if __name__ == "__main__":
    main()
