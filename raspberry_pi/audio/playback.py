"""
AudioPlayer — plays WAV/PCM audio to the MAX98357A amp via aplay subprocess.

Same pattern as arecord in capture.py: shell out rather than use sounddevice,
because the I2S amp path is unreliable through PortAudio on Pi 5.

Mic/amp coordination via audio_mode GPIO: exclusive() switches to speak mode
(mics off, amp on), plays, then restores listen mode (mics on, amp off).
"""
from __future__ import annotations

import subprocess
from contextlib import contextmanager
from pathlib import Path

from . import config
from .scripts.audio_mode import listen as _listen, speak as _speak


class AudioPlayer:
    def play_wav(self, path: str | Path) -> None:
        """Play a WAV file through the amp."""
        with self.exclusive():
            subprocess.run(
                ["aplay", "-D", config.PLAYBACK_DEVICE, str(path)],
                check=True,
                stderr=subprocess.DEVNULL,
            )

    def play_pcm(self, pcm: bytes, sample_rate: int, channels: int = 1) -> None:
        """Play raw int16 PCM bytes through the amp."""
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
        """Switch to speak mode (amp on, mics off) for the duration of playback."""
        _speak()
        try:
            yield
        finally:
            _listen()
