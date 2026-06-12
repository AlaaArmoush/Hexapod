# An Autonomous Hexapod

An 18-DOF hexapod robot with a conversational AI brain. An ESP32 handles real-time inverse kinematics, tripod gait, and animated OLED expressions. A Raspberry Pi 5 runs wake-word detection, speech-to-text, a local LLM (Gemma 4), text-to-speech, and stereo-vision person tracking — all without cloud services.

---

## Hardware

| Component | Role |
|-----------|------|
| ESP32 DevKit V3 | Real-time controller: IK, gait, servos, display |
| Raspberry Pi 5 (8 GB) | Companion computer: voice, vision, AI |
| 2× PCA9685 | PWM servo drivers (I2C 0x40 / 0x41) |
| 19× MG996R servo | 18 leg joints + 1 camera pan |
| Luxonis OAK-D | Stereo depth camera + RGB |
| 4× INMP441 | I2S MEMS microphones |
| MAX98357A | I2S audio amplifier |
| SH1107 128×128 OLED | Animated robot face |
| DFRobot UPS HAT | Uninterruptible power for the Pi |

The chassis is a four-level 3D-printed PLA stack. Level 1 (base + legs) starts from an [open-source hexapod frame](https://www.printables.com/model/606030-3d-printed-hexapod); levels 2–4 are original designs.

---

## Architecture

```
[ Microphones ]  [ OAK-D Camera ]
       |                 |
  Wake Word / STT    PersonTracker / ObjectSearcher
       |                 |
  [ Voice Pipeline — Raspberry Pi 5 ]
       |
  fast_robot_intent ──► skip LLM
  search_intent     ──► skip LLM
       |
  LlamaClient (Gemma 4 @ llama-server)
       |
  agent_validator
       |
  SerialRobotBridge ──► USB Serial (115200 baud)
       |
  [ ESP32 Firmware ]
  command_parser → command_router → robot_controller
       |
  legIK() → servo_driver → 2× PCA9685 → 18 servos
```

The host sends **semantic intents only** — never raw servo angles. The ESP32 rejects any command containing `servo`, `angle`, `pwm`, `board`, or `channel` fields.

---

## Repository Layout

```
src/                  ESP32 firmware (C++/Arduino via PlatformIO)
include/              Firmware headers (config.h, types.h, ik.h …)
bridge/               Python serial bridge and command builders
agent/                LLM agent loop, validator, tool executor
camera/               OAK-D provider, HostDetector, PersonTracker, ObjectSearcher
raspberry_pi/         Voice pipeline, STT, TTS, wake word, audio hardware
scripts/              CLI tools and debug utilities
tests/                Python unit tests (no hardware required)
docs/                 Reference documentation
```

---

## Setup

### Firmware (ESP32)

Install [PlatformIO](https://platformio.org/), then:

```bash
pio run                           # build only
pio run --target upload           # build and flash
pio device monitor                # open serial monitor
pio run --target upload && pio device monitor
```

### Python (Raspberry Pi / laptop)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Additional Pi-only packages:
```bash
pip install moonshine-voice piper-tts
python -m moonshine_voice.download --language en --stt
```

Download the TTS voice (run once):
```bash
mkdir -p assets/voices
wget -O assets/voices/en_US-ryan-high.onnx \
  "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ryan/high/en_US-ryan-high.onnx"
wget -O assets/voices/en_US-ryan-high.onnx.json \
  "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ryan/high/en_US-ryan-high.onnx.json"
python scripts/generate_canned_lines.py
```

### LLM Server (for full agent mode)

```bash
llama-server -m ~/models/gemma4/gemma-4-E2B-it-Q8_0.gguf \
  -c 2048 --reasoning off --temp 0.2 --top-k 20 --top-p 0.9 \
  --n-predict 100 -t 8 --host 127.0.0.1 --port 8080
```

---

## Running

### Agent CLI (text commands, no microphone needed)

```bash
# Mock mode — no llama-server required
python3 scripts/run_agent_cli.py --mock-llm --once "hello"

# Validate a command and print the serial JSON it would send
python3 scripts/run_agent_cli.py --once "wave" --robot-dry-run

# Real hardware
python3 scripts/run_agent_cli.py --enable-robot --port /dev/ttyUSB0 --once "stand"

# Interactive session
python3 scripts/run_agent_cli.py
```

### Voice Pipeline (Raspberry Pi)

```bash
# Listen + agent, no robot output
python -m raspberry_pi.pipeline

# Full pipeline: wake word + robot
python -m raspberry_pi.pipeline --wake-word --enable-robot --port /dev/ttyUSB0

# Full pipeline + person tracking and object search
python -m raspberry_pi.pipeline --wake-word --enable-camera --enable-robot --port /dev/ttyUSB0

# Remote llama-server
python -m raspberry_pi.pipeline --base-url http://HOST:8080
```

### STT only (mic test)

```bash
python -m raspberry_pi.audio.stt
```

### Camera debug preview

```bash
python scripts/tracking_preview.py
```

---

## Tests

Tests do not require a connected ESP32, llama-server, camera, or microphone.

```bash
python3 -m pytest tests/ -v
python3 -m pytest tests/test_agent_loop.py -v
```

---

## Key Capabilities

| Feature | How it works |
|---------|-------------|
| 8-directional walking | Tripod gait with phase-based foot trajectories and IK |
| Body rotation | All legs drive in a circular arc around the body centre |
| Gestures | wave, lean, nod, shake, look, blink |
| 38 OLED face states | Automatic face–motion coupling (`syncFaceToMode`) |
| Wake word | "Hey Heksah" via openWakeWord ONNX model |
| Speech-to-text | Moonshine streaming (on-device, 16 kHz) |
| Text-to-speech | Piper neural TTS + pre-rendered canned lines |
| Conversational AI | Gemma 4 via llama-server, all local |
| Fast-intent bypass | Rule-based classifier skips the LLM for simple commands |
| Person tracking + approach | YOLOv8n + EMA tracker + ApproachController |
| Object search | "find the cup" → ObjectSearcher scans pan × body rotations |
| Tool system | time, date, battery, web search, reminders, depth probe, scene observation |

---

## Voice Command Examples

| You say | What happens |
|---------|-------------|
| "Hey Heksah" | Wake word — robot pans toward you, approaches, greets |
| "Walk forward two steps" | Fast-intent → gait forward, no LLM |
| "Turn left 90 degrees" | Fast-intent → rotate left |
| "Wave" | Fast-intent → wave gesture |
| "Find the bottle" | search_intent → ObjectSearcher|
| "What time is it?" | LLM → `get_time` tool |
| "How are you feeling?" | LLM → conversational response + face |

---

## Documentation

| File | Contents |
|------|---------|
| [docs/CAMERA_SYSTEM.md](docs/CAMERA_SYSTEM.md) | Provider, HostDetector, tracker, approach, object search |
| [docs/VOICE_PIPELINE.md](docs/VOICE_PIPELINE.md) | State machine, audio hardware, wake word, greet-and-approach |
| [docs/LOCAL_GEMMA_AGENT.md](docs/LOCAL_GEMMA_AGENT.md) | Agent loop, fast-intent, validator, tool registry |
| [docs/AGENT_OUTPUT_CONTRACT.md](docs/AGENT_OUTPUT_CONTRACT.md) | JSON schema the LLM must produce |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Full system architecture overview |
| [docs/RASPBERRY_PI_AUDIO_SETUP.md](docs/RASPBERRY_PI_AUDIO_SETUP.md) | I2S mic and amp wiring, ALSA device names, GPIO audio mode switching |

---
