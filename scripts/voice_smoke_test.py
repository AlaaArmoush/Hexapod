#!/usr/bin/env python3
"""
Manual end-to-end voice smoke test — echo mode, no LLM.

Speak a phrase; hear the canned filler ("on_it") then your phrase played back
through Piper via the MAX98357A amp. Mics are confirmed muted during playback
because AudioPlayer.exclusive() switches GPIO17/27 on every play call.

Run from repo root:
    python scripts/voice_smoke_test.py

Ctrl-C to stop.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from raspberry_pi.audio.pipeline import VoicePipeline


def main() -> int:
    print("Voice smoke test — echo mode. Speak a phrase, Ctrl-C to stop.")
    VoicePipeline().start()   # agent_fn=None → echoes transcript back through Piper
    return 0


if __name__ == "__main__":
    sys.exit(main())
