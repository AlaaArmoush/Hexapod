from __future__ import annotations

import wave
from pathlib import Path

from . import config


class PiperTTS:
    def __init__(
        self,
        voice_path: str | Path = config.VOICE_ONNX,
        config_path: str | Path = config.VOICE_JSON,
    ) -> None:
        from piper import PiperVoice
        self.voice = PiperVoice.load(str(voice_path), config_path=str(config_path))

    def synthesize(self, text: str) -> tuple[bytes, int]:
        """Return raw int16 PCM bytes and sample rate — no playback."""
        syn_config = None
        if config.TTS_LENGTH_SCALE is not None:
            from piper.config import SynthesisConfig
            syn_config = SynthesisConfig(length_scale=config.TTS_LENGTH_SCALE)
        chunks = [c.audio_int16_bytes for c in self.voice.synthesize(text, syn_config)]
        return b"".join(chunks), self.voice.config.sample_rate

    def synthesize_to_wav(self, text: str, path: str | Path) -> None:
        """Write a valid WAV file at path."""
        pcm, sr = self.synthesize(text)
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)   # int16
            wf.setframerate(sr)
            wf.writeframes(pcm)

    def say(self, text: str, player=None) -> None:
        """Synthesize and play through AudioPlayer (import lazily to avoid circular dep)."""
        if player is None:
            from .playback import AudioPlayer
            player = AudioPlayer()
        pcm, sr = self.synthesize(text)
        player.play_pcm(pcm, sr)
