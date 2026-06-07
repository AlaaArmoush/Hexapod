from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

import numpy as np
import sounddevice as sd

SAMPLE_RATE_OWW = 16000   # openwakeword requirement
# [MOCK]
CHANNELS_LAPTOP = 1
CHUNK_FRAMES = 1280       # ~80 ms at 16 kHz
WAKEWORD_THRESHOLD = 0.3

WakeCallback = Callable[[str, float], None]


class WakeWordDetector:
    """
    Streams audio from `device`, runs openwakeword frame-by-frame,
    and calls `on_wakeword(model_name, score)` when confidence crosses the threshold.
    On Pi: 4-channel 48 kHz → downsample CH0 to 16 kHz.
    """

    def __init__(
        self,
        model_path: Path,
        on_wakeword: WakeCallback,
        threshold: float = WAKEWORD_THRESHOLD,
        device: int | None = None,
    ) -> None:
        from openwakeword.model import Model 

        self._model = Model(wakeword_model_paths=[str(model_path)])
        self._on_wakeword = on_wakeword
        self._threshold = threshold
        self._device = device
        self._stream: sd.InputStream | None = None
        self._lock = threading.Lock()
        self._buffer = np.array([], dtype=np.int16)

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info: object, status: object) -> None:
        if status:
            print(f"[detector] audio status: {status}")
        mono = indata[:, 0].copy()
        pcm = (mono * 32767).astype(np.int16)
        with self._lock:
            self._buffer = np.concatenate([self._buffer, pcm])
            while len(self._buffer) >= CHUNK_FRAMES:
                chunk = self._buffer[:CHUNK_FRAMES]
                self._buffer = self._buffer[CHUNK_FRAMES:]
                self._process_chunk(chunk)

    def _process_chunk(self, chunk: np.ndarray) -> None:
        scores = self._model.predict(chunk)
        for model_name, score in scores.items():
            if score >= self._threshold:
                self._on_wakeword(model_name, float(score))

    def start(self) -> None:
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE_OWW,
            channels=CHANNELS_LAPTOP, # [MOCK]
            dtype="float32",
            blocksize=CHUNK_FRAMES,
            device=self._device,
            callback=self._audio_callback,
        )
        self._stream.start()

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
