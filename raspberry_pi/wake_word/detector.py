from __future__ import annotations

import queue
import subprocess
import sys
import threading
from pathlib import Path
from typing import Callable

import numpy as np
from scipy.signal import resample_poly

SAMPLE_RATE_HW = 48000
SAMPLE_RATE_OWW = 16000
_DOWNSAMPLE = SAMPLE_RATE_HW // SAMPLE_RATE_OWW   # = 3
CHANNELS_PI = 4
OWW_CHUNK_FRAMES = 1280                            # ~80 ms at 16 kHz
HW_CHUNK_FRAMES = OWW_CHUNK_FRAMES * _DOWNSAMPLE  # = 3840 frames at 48 kHz
_BYTES_PER_FRAME = CHANNELS_PI * 4                 # S32_LE = 4 bytes/sample
_CHUNK_BYTES = HW_CHUNK_FRAMES * _BYTES_PER_FRAME
WAKEWORD_THRESHOLD = 0.3

_ALSA_DEVICE = "plughw:0,1"

# (model_name, score, direction)
WakeCallback = Callable[[str, float, str], None]


class WakeWordDetector:
    """
    Streams 4-channel 48 kHz audio from the Pi soundcard via arecord,
    downsamples CH0 to 16 kHz for openwakeword, feeds all 4 channels to
    RealDirectionEstimator.  Calls on_wakeword(model_name, score, direction)
    when confidence crosses the threshold.
    """

    def __init__(
        self,
        model_path: Path,
        on_wakeword: WakeCallback,
        threshold: float = WAKEWORD_THRESHOLD,
        device: int | None = None,  # unused — kept for API compat; always uses plughw:0,1
        debug: bool = False,
    ) -> None:
        from openwakeword.model import Model
        self._model = Model(wakeword_model_paths=[str(model_path)])
        self._on_wakeword = on_wakeword
        self._threshold = threshold
        self._debug = debug
        self._proc: subprocess.Popen | None = None
        self._reader_thread: threading.Thread | None = None
        self._worker_thread: threading.Thread | None = None
        self._queue: queue.Queue[bytes] = queue.Queue(maxsize=50)
        self._running = False
        self._peak: float = 0.0

        from raspberry_pi.wake_word.direction import RealDirectionEstimator
        self._direction_est = RealDirectionEstimator()

    def _reader(self) -> None:
        assert self._proc is not None
        self._proc.stdout.read(44)  # skip WAV header
        while self._running:
            data = self._proc.stdout.read(_CHUNK_BYTES)
            if not data or len(data) < _CHUNK_BYTES:
                print(f"[detector] reader ended", file=sys.stderr)
                break
            try:
                self._queue.put_nowait(data)
            except queue.Full:
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    pass
                self._queue.put_nowait(data)

    def _worker(self) -> None:
        while self._running or not self._queue.empty():
            try:
                data = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue

            pcm = np.frombuffer(data, dtype="<i4").reshape(-1, CHANNELS_PI)
            multichannel = pcm.astype(np.float32) / (2**31)

            self._direction_est.update(multichannel)

            ch0_16k = resample_poly(multichannel[:, 0], up=1, down=_DOWNSAMPLE).astype(np.float32)
            chunk_int16 = (ch0_16k * 32767).astype(np.int16)

            scores = self._model.predict(chunk_int16)
            for model_name, score in scores.items():
                if self._debug and score > self._peak:
                    self._peak = score
                    print(f"\r[detector] peak score={score:.4f} (threshold={self._threshold})", end="", file=sys.stderr)
                if score >= self._threshold:
                    direction = self._direction_est.estimate()
                    self._direction_est.reset()
                    self._on_wakeword(model_name, float(score), direction)

    def start(self) -> None:
        self._proc = subprocess.Popen(
            ["arecord", "-D", _ALSA_DEVICE, "-f", "S32_LE", "-r", str(SAMPLE_RATE_HW), "-c", str(CHANNELS_PI), "-"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        self._running = True
        self._reader_thread = threading.Thread(target=self._reader, daemon=True)
        self._worker_thread = threading.Thread(target=self._worker, daemon=True)
        self._reader_thread.start()
        self._worker_thread.start()

    def stop(self) -> None:
        self._running = False
        if self._proc is not None:
            self._proc.terminate()
            self._proc.wait()
            self._proc = None
        if self._reader_thread is not None:
            self._reader_thread.join(timeout=2)
            self._reader_thread = None
        if self._worker_thread is not None:
            self._worker_thread.join(timeout=2)
            self._worker_thread = None
