from pathlib import Path

# Hexapod audio hardware — card 0 combined I2S overlay
# Playback: card 0, device 0 (MAX98357A amp)
# Capture:  card 0, device 1 (4x INMP441 DMIC)
PLAYBACK_DEVICE = "plughw:0,0"
CAPTURE_DEVICE = "plughw:0,1"   # ALSA: hexapod card 0, device 1 (4x INMP441 DMIC)

CAPTURE_RATE = 48000
CAPTURE_CHANNELS = 4
STT_SAMPLE_RATE = 16000     # Moonshine native rate

# STT — moonshine-voice
# Downloaded via: python -m moonshine_voice.download --language en --stt
MOONSHINE_MODEL_NAME = "medium-streaming-en"
MOONSHINE_MODEL_ARCH = 5    # ModelArch value reported by download
MOONSHINE_MODEL_PATH = (
    Path.home() / ".cache" / "moonshine_voice"
    / "download.moonshine.ai" / "model"
    / MOONSHINE_MODEL_NAME / "quantized"
)
