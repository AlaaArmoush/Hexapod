# Hexapod audio hardware — card 0 combined I2S overlay
# Playback: card 0, device 0 (MAX98357A amp)
# Capture:  card 0, device 1 (4x INMP441 DMIC)
PLAYBACK_DEVICE = "plughw:0,0"
CAPTURE_DEVICE_INDEX = 1    # sounddevice index — same as wake_word AUDIO_DEVICE=1

CAPTURE_RATE = 48000
CAPTURE_CHANNELS = 4
STT_SAMPLE_RATE = 16000     # Moonshine native rate

# STT — moonshine-voice streaming
# Model names: "base-en" (better accuracy) or "tiny-en" (~2x faster, lower accuracy)
# Download first: python -m moonshine_voice.download --language en
MOONSHINE_MODEL_NAME = "base-en"
