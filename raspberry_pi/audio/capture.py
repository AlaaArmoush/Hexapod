"""
AudioCapture — streams 4-ch 48 kHz from the hexapod I2S card,
downsamples channel 0 to mono 16 kHz, and feeds float32 chunks
to a callback.  Manages GPIO17 (mic power) and GPIO27 (amp SD).
"""
from __future__ import annotations

from typing import Callable

import numpy as np
import sounddevice as sd
from scipy.signal import resample_poly

from . import config
from .scripts.audio_mode import listen as _audio_listen, off as _audio_off

_DOWNSAMPLE = config.CAPTURE_RATE // config.STT_SAMPLE_RATE  # 48000/16000 = 3
_CHUNK_MS = 100
_HW_FRAMES = int(config.CAPTURE_RATE * _CHUNK_MS / 1000)     # 4800 frames @ 48 kHz


class AudioCapture:
    def __init__(self, on_chunk: Callable[[np.ndarray], None]) -> None:
        self._on_chunk = on_chunk
        self._stream: sd.InputStream | None = None

    def _callback(self, indata: np.ndarray, _frames: int, _time: object, status: object) -> None:
        if status:
            print(f"[capture] {status}")
        ch0 = indata[:, 0].copy()
        mono_16k = resample_poly(ch0, up=1, down=_DOWNSAMPLE).astype(np.float32)
        self._on_chunk(mono_16k)

    def start(self) -> None:
        _audio_listen()
        self._stream = sd.InputStream(
            samplerate=config.CAPTURE_RATE,
            channels=config.CAPTURE_CHANNELS,
            dtype="float32",
            blocksize=_HW_FRAMES,
            device=config.CAPTURE_DEVICE_INDEX,
            callback=self._callback,
        )
        self._stream.start()

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        _audio_off()
