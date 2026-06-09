# Hexapod audio hardware — card 0 combined I2S overlay
# Playback: card 0, device 0 (MAX98357A amp)
# Capture:  card 0, device 1 (4x INMP441 DMIC)
PLAYBACK_DEVICE = "plughw:0,0"
CAPTURE_DEVICE_INDEX = 1    # sounddevice index — same as wake_word AUDIO_DEVICE=1

CAPTURE_RATE = 48000
CAPTURE_CHANNELS = 4
STT_SAMPLE_RATE = 16000     # Moonshine native rate

# STT — moonshine-onnx
MOONSHINE_MODEL = "moonshine/base"   # swap to "moonshine/tiny" for ~2x speed, lower accuracy

# VAD (energy-based, tunable)
VAD_ENERGY_THRESHOLD = 0.01     # RMS: below this = silence
VAD_SPEECH_PAD_MS    = 600      # ms of trailing silence before utterance is closed
VAD_MIN_SPEECH_MS    = 200      # shorter clips are discarded (noise / breath)
