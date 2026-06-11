from __future__ import annotations

import queue
import subprocess
import sys
import threading
import time
from typing import Callable

import numpy as np
from scipy.signal import resample_poly

from . import config
from .scripts.audio_mode import listen as _audio_listen, off as _audio_off

_CHUNK_MS = 100
_CHUNK_FRAMES = int(config.CAPTURE_RATE * _CHUNK_MS / 1000)   # 4800 frames @ 48 kHz
_BYTES_PER_FRAME = config.CAPTURE_CHANNELS * 4                 # S32_LE = 4 bytes/sample
_CHUNK_BYTES = _CHUNK_FRAMES * _BYTES_PER_FRAME
_DOWNSAMPLE = config.CAPTURE_RATE // config.STT_SAMPLE_RATE    # 3


class AudioCapture:
    def __init__(self, on_chunk: Callable[[np.ndarray], None]) -> None:
        self._on_chunk = on_chunk
        self._proc: subprocess.Popen | None = None
        self._reader_thread: threading.Thread | None = None
        self._worker_thread: threading.Thread | None = None
        self._queue: queue.Queue[bytes] = queue.Queue(maxsize=100)
        self._running = False

    def _reader(self) -> None:
        # Skip the 44-byte WAV header arecord writes before PCM data
        self._proc.stdout.read(44)
        while self._running:
            data = self._proc.stdout.read(_CHUNK_BYTES)
            if not data or len(data) < _CHUNK_BYTES:
                print(f"[capture] reader ended ({len(data) if data else 0}/{_CHUNK_BYTES} bytes)", file=sys.stderr)
                break
            try:
                self._queue.put_nowait(data)
            except queue.Full:
                # Drop oldest chunk to make room rather than blocking the reader
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
            pcm = np.frombuffer(data, dtype="<i4").reshape(-1, config.CAPTURE_CHANNELS)
            ch0 = np.clip(pcm[:, 0].astype(np.float32) / (2**31) * config.MIC_GAIN, -1.0, 1.0)
            mono_16k = resample_poly(ch0, up=1, down=_DOWNSAMPLE).astype(np.float32)
            self._on_chunk(mono_16k)

    def start(self) -> None:
        _audio_listen()
        time.sleep(0.1)
        self._proc = subprocess.Popen(
            [
                "arecord",
                "-D", config.CAPTURE_DEVICE,
                "-f", "S32_LE",
                "-r", str(config.CAPTURE_RATE),
                "-c", str(config.CAPTURE_CHANNELS),
                "-",
            ],
            stdout=subprocess.PIPE,
            stderr=None,
        )
        self._running = True
        self._reader_thread = threading.Thread(target=self._reader, daemon=True)
        self._worker_thread = threading.Thread(target=self._worker, daemon=True)
        self._reader_thread.start()
        self._worker_thread.start()

    def flush(self) -> None:
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

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
        _audio_off()
