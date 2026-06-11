from __future__ import annotations

import contextlib
import os
import sys
import time
from typing import Callable

import numpy as np

from . import config


@contextlib.contextmanager
def _suppress_fd2():
    fd = os.open(os.devnull, os.O_WRONLY)
    saved = os.dup(2)
    os.dup2(fd, 2)
    try:
        yield
    finally:
        os.dup2(saved, 2)
        os.close(saved)
        os.close(fd)


class MoonshineSTT:
    def __init__(self, on_final: Callable[[str], None]) -> None:
        from moonshine_voice import Transcriber, TranscriptEventListener, ModelArch

        class _Listener(TranscriptEventListener):
            def on_line_text_changed(self_, event) -> None:
                print(f"[stt] partial: {event.line.text!r}", file=sys.stderr, end="\r")

            def on_line_completed(self_, event) -> None:
                text = event.line.text.strip()
                print(f"\n[stt] final: {text!r}", file=sys.stderr)
                if text:
                    on_final(text)

        with _suppress_fd2():
            self._t = Transcriber(
                model_path=str(config.MOONSHINE_MODEL_PATH),
                model_arch=ModelArch(config.MOONSHINE_MODEL_ARCH),
            )
        self._t.add_listener(_Listener())

    def start(self) -> None:
        self._paused = False
        self._t.start()

    def stop(self) -> None:
        self._t.stop()

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    def feed(self, chunk: np.ndarray) -> None:
        if not getattr(self, "_paused", False):
            self._t.add_audio(chunk, config.STT_SAMPLE_RATE)


def run_live() -> None:
    """Run STT from the live mic — press Ctrl-C to stop."""
    from .capture import AudioCapture

    def on_final(text: str) -> None:
        print(f"\n>>> {text}\n")

    print(f"Loading Moonshine model '{config.MOONSHINE_MODEL_NAME}' from {config.MOONSHINE_MODEL_PATH} …")
    stt = MoonshineSTT(on_final=on_final)
    cap = AudioCapture(on_chunk=stt.feed)

    stt.start()
    cap.start()
    print("Listening — speak a command, Ctrl-C to quit.\n")
    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n[stt] stopping")
    finally:
        stt.stop()
        cap.stop()


if __name__ == "__main__":
    run_live()
