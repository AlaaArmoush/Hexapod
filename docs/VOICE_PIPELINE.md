# Voice Pipeline

## Scope

This document covers the Raspberry Pi audio and voice interaction stack:
hardware wiring, audio I/O, wake-word detection, direction estimation,
STT, TTS, canned lines, and the pipeline state machine.

## Hardware

| Component | Device | Notes |
|-----------|--------|-------|
| Microphones | 4× INMP441 DMIC (I2S) | card 0 device 1: `plughw:0,1` |
| Speaker amp | MAX98357A (I2S) | card 0 device 0: `plughw:0,0` |
| Mic power | GPIO17 | pull low = ON |
| Amp enable | GPIO27 | pull high = ON |

`dtoverlay -l` reports nothing even when the overlay is active — the Pi 5
bootloader applies overlays before the kernel. This is expected.

Channel → physical direction mapping for the 4-mic array:

| Channel | Direction | I2S config |
|---------|-----------|------------|
| CH0 | FRONT | pin15/GND |
| CH1 | RIGHT | pin15/3V3 |
| CH2 | LEFT | pin38/GND |
| CH3 | BACK | pin38/3V3 |

## Audio Mode Switching

File: `raspberry_pi/audio/scripts/audio_mode.py`

Before every TTS playback call, `speak()` disables the mic (GPIO17 high) and
enables the amp (GPIO27 high). After playback, `listen()` reverses this.
Switching at the GPIO level means no AEC is required.

`playback.py` calls `audio_mode.speak()` before and `audio_mode.listen()`
after every `play_wav` / `play_pcm` call automatically.

## Audio Capture

File: `raspberry_pi/audio/capture.py`

`AudioCapture` wraps an `arecord` subprocess at `plughw:0,1`. It delivers
16-bit PCM chunks to an `on_chunk` callback. The device string is used
directly — integer index lookup fails on Pi 5 because `query_devices()` returns
empty; string names always work.

## STT

File: `raspberry_pi/audio/stt.py`

`MoonshineSTT` runs local streaming transcription using the
`medium-streaming-en` model (arch=5) at 16 kHz. The model lives at
`~/.cache/moonshine_voice/download.moonshine.ai/model/medium-streaming-en/quantized`.

`feed(chunk)` accepts raw PCM. `pause()` / `resume()` gate transcription so
audio captured while the robot is speaking is discarded.

## TTS

File: `raspberry_pi/audio/tts.py`

`PiperTTS` synthesises speech offline using `en_US-ryan-high` stored at
`assets/voices/` (gitignored — regenerate with the `wget` commands in
CLAUDE.md). `TTS_LENGTH_SCALE` controls speed (`None` = voice default).

After changing the voice or `TTS_LENGTH_SCALE`, regenerate canned lines:

```bash
python scripts/generate_canned_lines.py --force
```

## Canned Lines

File: `scripts/generate_canned_lines.py`

Pre-rendered WAVs live at `assets/canned/` (gitignored). They provide
zero-latency responses for high-frequency events:

| Name | When played |
|------|-------------|
| `boot_ready` | On pipeline startup |
| `wake_ack` | Immediately after wake word fires |
| `okay` | Generic acknowledgement |
| `approaching` | Before ApproachController starts |
| `greet_1/2/3` | Randomly chosen on person arrival |
| `sorry` | On STT error or LLM failure |
| `goodbye` | On clean shutdown |

## Wake-Word Detector

File: `raspberry_pi/wake_word/detector.py`

`WakeWordDetector` streams 48 kHz 4-channel audio via `sounddevice` using
`device="hw:0,1"`. On each frame it:

1. Downsamples CH0 to 16 kHz for openwakeword inference (run in a worker
   thread to avoid blocking the audio callback).
2. Feeds all 4 channels to `RealDirectionEstimator`.
3. Fires `on_wakeword(model, score, direction)` when score exceeds threshold.

| Parameter | Value |
|-----------|-------|
| Model | `hey_hek_sah.onnx` (custom) |
| Threshold | 0.3 |
| Input gain | 4.0 |

## Direction Estimation

File: `raspberry_pi/wake_word/direction.py`

`RealDirectionEstimator` maintains a rolling energy window over all 4 DMIC
channels. The channel with the highest energy is mapped to a cardinal direction:
`front | right | left | back`. This gives the pipeline a coarse initial guess
for where to pan the camera.

The direction estimate is intentionally coarse — the camera scan step that
follows will correct it if wrong.

## Pipeline State Machine

File: `raspberry_pi/pipeline.py`

`VoicePipeline` has five states:

```text
IDLE
  ↓ (startup)
WAKE_LISTENING
  ↓ (wake word fires)
LISTENING
  ↓ (transcript arrives)
THINKING
  ↓ (agent returns)
SPEAKING
  ↓ (playback done / cooldown elapsed)
WAKE_LISTENING
```

### IDLE

Initial state. Transitions to `WAKE_LISTENING` on `run()`.

### WAKE_LISTENING

Wake-word detector and audio stream are active. On threshold crossing:

1. Direction estimate is captured.
2. Detector is stopped.
3. Camera pans toward estimated direction (if `--enable-camera`).
4. Pipeline tries to acquire a person within 2 s.

If person found: `_greet_and_approach()` — see below.
If person not found: scan other pan positions (`_scan_for_person()`).
If still not found: start STT, show `listening` face.

### LISTENING

STT stream is active. Transcript arrives via `on_transcript()`. A
`POST_SPEAK_COOLDOWN = 1.2 s` gate discards audio captured while the robot
was speaking.

### THINKING

STT is paused. The transcript is processed by:

1. `search_intent.match_search_intent()` — if matched, calls `ObjectSearcher`
   directly and skips the LLM.
2. `agent_fn()` — the full agent pipeline (fast-intent → LLM → validator →
   tool executor).

### SPEAKING

TTS output is played. Info-tool faces (`clock`, `calendar`, `timer`,
`reminder`, `memory`, `battery`, `system`) linger on the display for
`LINGER_HOLD_S = 2.5 s` so the user can read them. After the cooldown the
pipeline returns to `WAKE_LISTENING`.

## Greet and Approach Sequence

When the wake word fires and a person is detected:

```text
1. Align body to face the camera pan position (_align_body_to_pan)
   → rotate firmware N cycles in direction of person
2. Wait 1.4 s for body rotation to complete
3. tracker.reset() — clear EMA from pre-turn angle
4. Send camera_pan center command
5. Wait 0.6 s for camera recentre + tracker re-lock
6. Re-acquire person (2 s timeout)
7. Play "approaching" canned line
8. Show walking face
9. ApproachController.run()
   → ARRIVED: play random greet_1/2/3, start STT conversation
   → LOST:    recover to WAKE_LISTENING
   → TIMEOUT: recover to WAKE_LISTENING
10. On BridgeError (serial drop): recover to WAKE_LISTENING without crash
```

## Pan → Body Rotation Table

The pipeline maps camera pan positions to body rotation commands so the robot
faces the detected person before approach. Rotation is quantised to 30°
firmware cycles.

| Pan position | Direction | Degrees |
|--------------|-----------|---------|
| `left` | left | 60° |
| `front_left` | left | 30° |
| `center` | — | 0° |
| `front_right` | right | 30° |
| `right` | right | 60° |

## Running the Pipeline

```bash
# Listen + agent, no robot
python -m raspberry_pi.pipeline

# Full pipeline: wake word + robot serial
python -m raspberry_pi.pipeline --wake-word --enable-robot --port /dev/ttyUSB0

# + person tracking / approach / search
python -m raspberry_pi.pipeline --wake-word --enable-camera --enable-robot --port /dev/ttyUSB0

# Remote llama-server
python -m raspberry_pi.pipeline --base-url http://HOST:8080
```
