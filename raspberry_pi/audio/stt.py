"""
MoonshineSTT — energy-VAD segmentation + moonshine-onnx transcription.

Accepts 16 kHz mono float32 chunks from AudioCapture.  Buffers audio while
speech is detected, then transcribes the full utterance once silence returns.

Install on Pi: pip install moonshine-onnx
"""
from __future__ import annotations

import sys
from typing import Callable

import numpy as np

from . import config


class MoonshineSTT:
    def __init__(self, on_final: Callable[[str], None]) -> None:
        from moonshine_onnx import MoonshineOnnxModel, load_tokenizer

        self._model = MoonshineOnnxModel(model_name=config.MOONSHINE_MODEL)
        self._tokenizer = load_tokenizer()
        self._on_final = on_final

        self._speech_buf: list[np.ndarray] = []
        self._in_speech = False
        self._silence_frames = 0

        # how many 100ms chunks of silence close an utterance
        self._silence_chunks_needed = int(
            config.VAD_SPEECH_PAD_MS / 100
        )
        self._min_speech_samples = int(
            config.VAD_MIN_SPEECH_MS / 1000 * config.STT_SAMPLE_RATE
        )

    def feed(self, chunk: np.ndarray) -> None:
        """Call with each 16 kHz mono float32 chunk from AudioCapture."""
        rms = float(np.sqrt(np.mean(chunk ** 2)))
        is_speech = rms > config.VAD_ENERGY_THRESHOLD

        if is_speech:
            if not self._in_speech:
                print("[stt] speech start", file=sys.stderr)
            self._in_speech = True
            self._silence_frames = 0

        if self._in_speech:
            self._speech_buf.append(chunk)

        if self._in_speech and not is_speech:
            self._silence_frames += 1
            if self._silence_frames >= self._silence_chunks_needed:
                self._flush()

    def _flush(self) -> None:
        audio = np.concatenate(self._speech_buf)
        self._speech_buf = []
        self._in_speech = False
        self._silence_frames = 0

        if len(audio) < self._min_speech_samples:
            print("[stt] discarded (too short)", file=sys.stderr)
            return

        print(f"[stt] transcribing {len(audio)/config.STT_SAMPLE_RATE:.1f}s …", file=sys.stderr)
        tokens = self._model.generate(audio)
        text = self._tokenizer.decode_batch(tokens)[0].strip()
        print(f"[stt] transcript: {text!r}", file=sys.stderr)
        if text:
            self._on_final(text)


def run_live() -> None:
    """Run STT from the live mic — press Ctrl-C to stop."""
    from .capture import AudioCapture

    def on_final(text: str) -> None:
        print(f"\n>>> {text}\n")

    stt = MoonshineSTT(on_final=on_final)
    cap = AudioCapture(on_chunk=stt.feed)

    print("Loading Moonshine model …")
    print(f"Model: {config.MOONSHINE_MODEL}")
    print("Listening — speak a command, Ctrl-C to quit.\n")

    cap.start()
    try:
        import time
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n[stt] stopping")
    finally:
        cap.stop()


if __name__ == "__main__":
    run_live()
