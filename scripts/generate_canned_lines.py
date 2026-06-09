#!/usr/bin/env python3
"""
Run once at setup and again after any voice change:
    python scripts/generate_canned_lines.py
    python scripts/generate_canned_lines.py --force   # re-render even if file exists
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from raspberry_pi.audio import config
from raspberry_pi.audio.tts import PiperTTS


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Re-render even if file exists")
    args = parser.parse_args()

    out_dir = Path(config.CANNED_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading voice from {config.VOICE_ONNX} …")
    tts = PiperTTS()

    for key, text in config.CANNED_LINES.items():
        path = out_dir / f"{key}.wav"
        if path.exists() and not args.force:
            print(f"  skip  {key}")
            continue
        print(f"  render {key!r}: {text!r}")
        tts.synthesize_to_wav(text, path)

    print(f"Done — {len(config.CANNED_LINES)} lines in {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
