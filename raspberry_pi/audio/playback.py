from __future__ import annotations

import subprocess
from contextlib import contextmanager
from pathlib import Path

from . import config
from .scripts.audio_mode import listen as _listen, speak as _speak


class AudioPlayer:
    def play_wav(self, path: str | Path) -> None:
        with self.exclusive():
            subprocess.run(
                ["aplay", "-D", config.PLAYBACK_DEVICE, str(path)],
                check=True,
                stderr=subprocess.DEVNULL,
            )

    def play_pcm(self, pcm: bytes, sample_rate: int, channels: int = 1) -> None:
        with self.exclusive():
            proc = subprocess.Popen(
                [
                    "aplay",
                    "-D", config.PLAYBACK_DEVICE,
                    "-f", "S16_LE",
                    "-r", str(sample_rate),
                    "-c", str(channels),
                    "-",
                ],
                stdin=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            proc.communicate(pcm)

    @contextmanager
    def exclusive(self):
        _speak()
        try:
            yield
        finally:
            _listen()
