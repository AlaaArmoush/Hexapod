from __future__ import annotations

import queue
import sys
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
WAKEWORD_MODEL_PATH = Path(__file__).resolve().parents[2] / "hey_hek_sah.onnx"

# ALSA string device name — works with sounddevice even when query_devices() returns nothing
AUDIO_DEVICE = "hw:0,1"

# (model_name, score, direction)
WakeCallback = Callable[[str, float, str], None]


class WakeWordDetector:
    def __init__(
        self,
        model_path: Path,
        on_wakeword: WakeCallback,
        threshold: float = WAKEWORD_THRESHOLD,
        device: str | int | None = AUDIO_DEVICE,
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
        self._chunk_queue: queue.Queue = queue.Queue(maxsize=20)
        self._worker_thread: threading.Thread | None = None

    def _audio_callback(self, indata: np.ndarray, _frames: int, _time_info: object, status: object) -> None:
        if status:
            print(f"[detector] audio status: {status}")
        self._direction_est.update(indata)
        ch0_16k = resample_poly(indata[:, 0].copy(), up=1, down=_DOWNSAMPLE).astype(np.float32)
        pcm = (ch0_16k * 32767).astype(np.int16)
        # Split into OWW-sized chunks and enqueue — never block the audio thread.
        with self._lock:
            self._buffer = np.concatenate([self._buffer, pcm])
            while len(self._buffer) >= OWW_CHUNK_FRAMES:
                chunk = self._buffer[:OWW_CHUNK_FRAMES]
                self._buffer = self._buffer[OWW_CHUNK_FRAMES:]
                try:
                    self._chunk_queue.put_nowait(chunk)
                except queue.Full:
                    pass  # drop oldest to keep latency low

    def _worker(self) -> None:
        while True:
            chunk = self._chunk_queue.get()
            if chunk is None:
                break
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
        self._worker_thread = threading.Thread(target=self._worker, daemon=True)
        self._worker_thread.start()
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
        if self._worker_thread is not None:
            self._chunk_queue.put(None)
            self._worker_thread.join(timeout=2.0)
            self._worker_thread = None
