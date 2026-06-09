from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

import numpy as np
import sounddevice as sd
from scipy.signal import resample_poly

SAMPLE_RATE_HW = 48000    # Pi hardware rate (hexapod soundcard)
SAMPLE_RATE_OWW = 16000   # openwakeword requirement
_DOWNSAMPLE = SAMPLE_RATE_HW // SAMPLE_RATE_OWW   # = 3
CHANNELS_PI = 4
OWW_CHUNK_FRAMES = 1280                            # ~80 ms at 16 kHz
HW_CHUNK_FRAMES = OWW_CHUNK_FRAMES * _DOWNSAMPLE  # = 3840 frames at 48 kHz
WAKEWORD_THRESHOLD = 0.3

# (model_name, score, direction) — direction is one of the strings from RealDirectionEstimator
WakeCallback = Callable[[str, float, str], None]


class WakeWordDetector:
    """
    Streams 4-channel 48 kHz audio from the Pi soundcard (DEVICE=1),
    downsamples CH0 to 16 kHz, and runs openwakeword frame-by-frame.
    Calls on_wakeword(model_name, score, direction) when confidence crosses the threshold.
    """

    def __init__(
        self,
        model_path: Path,
        on_wakeword: WakeCallback,
        threshold: float = WAKEWORD_THRESHOLD,
        device: int | None = None,
        debug: bool = False,
    ) -> None:
        from openwakeword.model import Model

        self._model = Model(wakeword_model_paths=[str(model_path)])
        self._on_wakeword = on_wakeword
        self._threshold = threshold
        self._device = device
        self._debug = debug
        self._stream: sd.InputStream | None = None
        self._lock = threading.Lock()
        self._buffer = np.array([], dtype=np.int16)
        self._peak: float = 0.0

        from raspberry_pi.wake_word.direction import RealDirectionEstimator
        self._direction_est = RealDirectionEstimator()

    def _audio_callback(self, indata: np.ndarray, _frames: int, _time_info: object, status: object) -> None:
        if status:
            print(f"[detector] audio status: {status}")
        # Feed raw multichannel audio to direction estimator before extracting CH0
        self._direction_est.update(indata)
        ch0 = indata[:, 0].copy()
        ch0_16k = resample_poly(ch0, up=1, down=_DOWNSAMPLE).astype(np.float32)
        pcm = (ch0_16k * 32767).astype(np.int16)
        with self._lock:
            self._buffer = np.concatenate([self._buffer, pcm])
            while len(self._buffer) >= OWW_CHUNK_FRAMES:
                chunk = self._buffer[:OWW_CHUNK_FRAMES]
                self._buffer = self._buffer[OWW_CHUNK_FRAMES:]
                self._process_chunk(chunk)

    def _process_chunk(self, chunk: np.ndarray) -> None:
        import sys
        scores = self._model.predict(chunk)
        for model_name, score in scores.items():
            if self._debug and score > self._peak:
                self._peak = score
                print(f"\r[detector] peak score={score:.4f} (threshold={self._threshold})", end="", file=sys.stderr)
            if score >= self._threshold:
                direction = self._direction_est.estimate()
                self._direction_est.reset()
                self._on_wakeword(model_name, float(score), direction)

    def start(self) -> None:
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE_HW,
            channels=CHANNELS_PI,
            dtype="float32",
            blocksize=HW_CHUNK_FRAMES,
            device=self._device,
            callback=self._audio_callback,
        )
        self._stream.start()

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
