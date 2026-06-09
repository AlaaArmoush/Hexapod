"""
AudioCapture — reads 4-ch 48 kHz audio from the hexapod DMIC via arecord,
downsamples channel 0 to mono 16 kHz, and feeds float32 chunks to a callback.
Uses arecord because PortAudio/sounddevice doesn't enumerate the I2S DMIC.
Manages GPIO17 (mic power) and GPIO27 (amp SD).
"""
from __future__ import annotations

import subprocess
import threading
from typing import Callable

import numpy as np
from scipy.signal import resample_poly

from . import config
from .scripts.audio_mode import listen as _audio_listen, off as _audio_off

_CHUNK_MS = 100
_CHUNK_FRAMES = int(config.CAPTURE_RATE * _CHUNK_MS / 1000)          # 4800 frames @ 48 kHz
_BYTES_PER_FRAME = config.CAPTURE_CHANNELS * 4                        # S32_LE = 4 bytes/sample
_CHUNK_BYTES = _CHUNK_FRAMES * _BYTES_PER_FRAME
_DOWNSAMPLE = config.CAPTURE_RATE // config.STT_SAMPLE_RATE           # 3


class AudioCapture:
    def __init__(self, on_chunk: Callable[[np.ndarray], None]) -> None:
        self._on_chunk = on_chunk
        self._proc: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None
        self._running = False

    def _reader(self) -> None:
        while self._running:
            data = self._proc.stdout.read(_CHUNK_BYTES)
            if not data or len(data) < _CHUNK_BYTES:
                break
            # S32_LE interleaved → float32 [-1, 1], take channel 0
            pcm = np.frombuffer(data, dtype="<i4").reshape(-1, config.CAPTURE_CHANNELS)
            ch0 = pcm[:, 0].astype(np.float32) / (2**31)
            mono_16k = resample_poly(ch0, up=1, down=_DOWNSAMPLE).astype(np.float32)
            self._on_chunk(mono_16k)

    def start(self) -> None:
        _audio_listen()
        self._proc = subprocess.Popen(
            [
                "arecord",
                "-D", config.CAPTURE_DEVICE,
                "-f", "S32_LE",
                "-r", str(config.CAPTURE_RATE),
                "-c", str(config.CAPTURE_CHANNELS),
                "-",   # write raw PCM to stdout
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        self._running = True
        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._proc is not None:
            self._proc.terminate()
            self._proc.wait()
            self._proc = None
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
        _audio_off()
