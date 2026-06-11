from __future__ import annotations

import wave
from pathlib import Path

from . import config


class CannedLines:
    def __init__(self, player=None) -> None:
        if player is None:
            from .playback import AudioPlayer
            player = AudioPlayer()
        self._player = player
        self._wavs: dict[str, tuple[bytes, int]] = {}

    def load(self) -> None:
        """Read all configured canned WAVs into memory. Raises if any are missing."""
        missing = []
        for key in config.CANNED_LINES:
            path = Path(config.CANNED_DIR) / f"{key}.wav"
            if not path.exists():
                missing.append(key)
                continue
            with wave.open(str(path), "rb") as wf:
                sr = wf.getframerate()
                pcm = wf.readframes(wf.getnframes())
            self._wavs[key] = (pcm, sr)
        if missing:
            raise FileNotFoundError(
                f"Missing canned WAVs (run scripts/generate_canned_lines.py): {missing}"
            )

    def play(self, key: str) -> None:
        """Play the canned line for key. Raises KeyError if unknown, FileNotFoundError if not loaded."""
        if key not in self._wavs:
            raise KeyError(f"Unknown canned line {key!r} — not in loaded set")
        pcm, sr = self._wavs[key]
        self._player.play_pcm(pcm, sr)
