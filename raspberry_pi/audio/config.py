from pathlib import Path

# Hexapod audio hardware — card 0 combined I2S overlay
# Playback: card 0, device 0 (MAX98357A amp)
# Capture:  card 0, device 1 (4x INMP441 DMIC)
PLAYBACK_DEVICE = "plughw:0,0"
CAPTURE_DEVICE = "plughw:0,1"   # ALSA: hexapod card 0, device 1 (4x INMP441 DMIC)

CAPTURE_RATE = 48000
CAPTURE_CHANNELS = 4
STT_SAMPLE_RATE = 16000     # Moonshine native rate
MIC_GAIN = 12.0             # software gain for INMP441 DMIC (adjust if too loud/quiet)

# STT — moonshine-voice
# Downloaded via: python -m moonshine_voice.download --language en --stt
MOONSHINE_MODEL_NAME = "medium-streaming-en"
MOONSHINE_MODEL_ARCH = 5    # ModelArch value reported by download
MOONSHINE_MODEL_PATH = (
    Path.home() / ".cache" / "moonshine_voice"
    / "download.moonshine.ai" / "model"
    / MOONSHINE_MODEL_NAME / "quantized"
)

# TTS — Piper
# Download voice: python -m piper.download_voices en_US-lessac-medium --data-dir assets/voices
_REPO_ROOT = Path(__file__).resolve().parents[2]
VOICES_DIR = _REPO_ROOT / "assets" / "voices"
VOICE_ONNX = VOICES_DIR / "en_US-ryan-high.onnx"
VOICE_JSON = VOICES_DIR / "en_US-ryan-high.onnx.json"
TTS_LENGTH_SCALE = None     # None = use voice default; higher = slower

# Canned lines — pre-rendered WAVs for zero-latency playback
# Generate: python scripts/generate_canned_lines.py
CANNED_DIR = _REPO_ROOT / "assets" / "canned"
CANNED_LINES: dict[str, str] = {
    "boot_ready": "Ready.",
    "wake_ack":   "Yes?",
    "listening":  "I'm listening.",
    "okay":       "Okay.",
    "on_it":      "On it.",
    "one_sec":    "Just a second.",
    "thinking":   "Let me think.",
    "working":    "Working on it.",
    "done":       "Done.",
    "not_caught": "Sorry, I didn't catch that.",
    "cant_do":    "I can't do that.",
    "error":      "Something went wrong.",
    "goodbye":    "Goodbye.",
}
