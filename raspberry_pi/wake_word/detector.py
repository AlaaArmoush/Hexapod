from __future__ import annotations

import contextlib
import os
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
# Digital gain applied to the mic signal before openwakeword. The DMIC level is quiet,
# so normal-volume speech under-drives the model — boosting the signal here lets it fire
# without lowering the threshold (which would raise false triggers). Tune if needed.
WAKEWORD_INPUT_GAIN = 4.0
WAKEWORD_MODEL_PATH = Path(__file__).resolve().parents[2] / "hey_hek_sah.onnx"

# ALSA string device name — works with sounddevice even when query_devices() returns nothing
AUDIO_DEVICE = "hw:0,1"

# (model_name, score, direction)
WakeCallback = Callable[[str, float, str], None]


@contextlib.contextmanager
def _suppress_fd2():
    """Redirect file-descriptor 2 (C-level stderr) to /dev/null.

    Python-level warnings.filterwarnings and ORT_LOGGING_LEVEL don't reach
    messages printed by onnxruntime's C++ layer before session creation, so
    we suppress them at the fd level around model initialisation only.
    """
    fd = os.open(os.devnull, os.O_WRONLY)
    saved = os.dup(2)
    os.dup2(fd, 2)
    try:
        yield
    finally:
        os.dup2(saved, 2)
        os.close(saved)
        os.close(fd)


class WakeWordDetector:
    def __init__(
        self,
        model_path: Path,
        on_wakeword: WakeCallback,
        threshold: float = WAKEWORD_THRESHOLD,
        device: str | int | None = AUDIO_DEVICE,
        debug: bool = False,
    ) -> None:
        with _suppress_fd2():
            from openwakeword.model import Model
            self._model = Model(wakeword_model_paths=[str(model_path)])
        self._on_wakeword = on_wakeword
        self._threshold = threshold
        self._device = device
        self._debug = debug
        self._stream: sd.InputStream | None = None
        self._peak: float = 0.0

        from raspberry_pi.wake_word.direction import RealDirectionEstimator
        self._direction_est = RealDirectionEstimator()
        # Queue carries raw 48 kHz float32 chunks — resampling happens in the worker
        # thread so the audio callback stays as fast as possible (prevents input overflow).
        self._chunk_queue: queue.Queue = queue.Queue(maxsize=20)
        self._worker_thread: threading.Thread | None = None
        self._buf16k = np.array([], dtype=np.int16)
        self._buf_lock = threading.Lock()

    def _audio_callback(self, indata: np.ndarray, _frames: int, _time_info: object, status: object) -> None:
        # Keep this callback minimal — any heavy work here causes input overflow.
        self._direction_est.update(indata)
        try:
            # Copy raw 48 kHz CH0 into the worker queue; resampling done there.
            self._chunk_queue.put_nowait(indata[:, 0].copy())
        except queue.Full:
            pass  # drop the chunk to keep latency low; better than blocking

    def _worker(self) -> None:
        while True:
            raw = self._chunk_queue.get()
            if raw is None:
                break
            # Resample 48 kHz → 16 kHz and apply gain here, off the audio thread.
            ch0 = raw.astype(np.float32) * WAKEWORD_INPUT_GAIN
            ch0_16k = resample_poly(ch0, up=1, down=_DOWNSAMPLE).astype(np.float32)
            np.clip(ch0_16k, -1.0, 1.0, out=ch0_16k)
            pcm = (ch0_16k * 32767).astype(np.int16)
            with self._buf_lock:
                self._buf16k = np.concatenate([self._buf16k, pcm])
                while len(self._buf16k) >= OWW_CHUNK_FRAMES:
                    chunk = self._buf16k[:OWW_CHUNK_FRAMES]
                    self._buf16k = self._buf16k[OWW_CHUNK_FRAMES:]
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
