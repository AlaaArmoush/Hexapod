# Raspberry Pi 5 Combined I2S Audio Setup

This is the current Hexapod voice assistant audio setup for Raspberry Pi 5.
It uses 4x INMP441 I2S microphones and a MAX98357A I2S amplifier/speaker on
the same I2S0 bus.

The old standalone 4-mic setup is no longer the target configuration. The
working arrangement is a combined Device Tree overlay plus GPIO-controlled
power/mute switching:

- Listening: amp OFF, mics ON.
- TTS playback: mics OFF, amp ON.

## Files

- Overlay source:
  `raspberry_pi/audio/overlays/hexapod-4mic-max98357a.dts`
- Overlay installer:
  `raspberry_pi/audio/scripts/install_combined_audio_overlay.sh`
- Setup verifier:
  `raspberry_pi/audio/scripts/verify_combined_audio_setup.sh`
- GPIO mode helper:
  `raspberry_pi/audio/scripts/audio_mode.py`
- 4-mic mapping test:
  `raspberry_pi/audio/scripts/four_mic_new_mapping_test.py`

Keep the overlay source under `raspberry_pi/audio/overlays/` even while there
is only one overlay. It is a Pi audio artifact, and the directory keeps DTS
sources separate from runtime scripts.

Keep this document in top-level `docs/`. The old `raspberry_pi/docs/` 4-mic
guide was for the pre-amplifier setup and has been retired to avoid two sources
of truth.

## Requirements

Run these on the Raspberry Pi before testing the audio stack:

```bash
sudo apt update
sudo apt install -y \
  device-tree-compiler \
  alsa-utils \
  sox \
  python3 \
  python3-venv \
  python3-pip \
  libportaudio2
```

What these provide:

| Package | Used for |
|---|---|
| `device-tree-compiler` | `dtc` for compiling the `.dts` overlay into `.dtbo` |
| `alsa-utils` | `aplay`, `arecord`, and `speaker-test` |
| `sox` | `soxi` for checking recorded WAV channel/sample details |
| `python3`, `python3-venv`, `python3-pip` | Python scripts and isolated mic-test environment |
| `libportaudio2` | Native PortAudio library required by Python `sounddevice` |

`pinctrl` is normally already present on Raspberry Pi OS. Check it with:

```bash
command -v pinctrl
```

For the 4-mic mapping script, create a venv and install the audio Python
packages:

```bash
python3 -m venv ~/mic-test-venv
source ~/mic-test-venv/bin/activate
pip install -r requirements.txt
```

## Hardware Constraints

A DFRobot UPS HAT is installed and occupies physical pins:

```text
3, 5, 25, 31, 36
```

Do not use those pins for the audio hardware.

## I2S Pin Usage

| Signal | GPIO | Physical pin | Use |
|---|---:|---:|---|
| I2S0 BCLK/SCLK | GPIO18 | 12 | Shared by mics and MAX98357A |
| I2S0 WS/LRCLK | GPIO19 | 35 | Shared by mics and MAX98357A |
| I2S0_SDI0 | GPIO20 | 38 | Mic input data lane 0 |
| I2S0_SDI1 | GPIO22 | 15 | Mic input data lane 1 |
| I2S0_SDO0 | GPIO21 | 40 | MAX98357A DIN |

## INMP441 Wiring

All microphones share:

| INMP441 pin | Raspberry Pi 5 |
|---|---|
| VDD | Switched 3.3V from PMOS drain |
| GND | GND |
| SCK | GPIO18 / physical pin 12 |
| WS | GPIO19 / physical pin 35 |

Electrical channel mapping:

| Channel | SD data lane | INMP441 L/R pin |
|---:|---|---|
| CH0 | GPIO20 / physical pin 38 | GND |
| CH1 | GPIO20 / physical pin 38 | 3.3V |
| CH2 | GPIO22 / physical pin 15 | GND |
| CH3 | GPIO22 / physical pin 15 | 3.3V |

Only the physical direction labels should change in Python if the mic placement
changes. The electrical channel rule stays fixed.

## MAX98357A Wiring

| MAX98357A pin | Connection |
|---|---|
| VIN | 5V |
| GND | GND |
| BCLK | GPIO18 / physical pin 12 |
| LRC | GPIO19 / physical pin 35 |
| DIN | GPIO21 / physical pin 40 |
| GAIN | GND |
| SD/shutdown | GPIO27 |
| Speaker | SPK+ / SPK- |

Amp control:

```bash
sudo pinctrl set 27 op dh   # amp ON
sudo pinctrl set 27 op dl   # amp OFF / muted
```

## Mic Power Switching

The INMP441 microphones are powered through an NDP6020P P-channel MOSFET.

| Connection | Wiring |
|---|---|
| PMOS source | Pi 3.3V |
| PMOS drain | All INMP441 VDD pins |
| PMOS gate | GPIO17 / physical pin 11 through 220 ohm resistor |
| Gate pull-up | 100k ohm resistor from gate to source / 3.3V |
| Mic GND | Pi GND, always connected |

Mic power logic:

```bash
sudo pinctrl set 17 op dh   # mics OFF
sudo pinctrl set 17 op dl   # mics ON
```

## Audio Mode Helper

The raw `pinctrl` commands above are the source of truth. For daily use and app
integration, this wrapper applies them in the correct order:

```bash
python3 raspberry_pi/audio/scripts/audio_mode.py listen  # amp OFF, mics ON
python3 raspberry_pi/audio/scripts/audio_mode.py speak   # mics OFF, amp ON
python3 raspberry_pi/audio/scripts/audio_mode.py off     # amp OFF, mics OFF
python3 raspberry_pi/audio/scripts/audio_mode.py status  # show GPIO17/GPIO27
```

## Install Overlay

On the Raspberry Pi:

```bash
cd ~/Hexapod
bash raspberry_pi/audio/scripts/install_combined_audio_overlay.sh
```

The script installs the system requirements listed above, compiles
`hexapod-4mic-max98357a.dts`, copies the resulting `.dtbo` into
`/boot/firmware/overlays/`, and backs up `/boot/firmware/config.txt`.

Edit `/boot/firmware/config.txt` after running the installer:

```ini
dtparam=i2c_arm=on
dtparam=i2s=on
#dtparam=spi=on

dtoverlay=hexapod-4mic-max98357a

# Disable old separate overlays
#dtoverlay=hexapod-4mic
#dtoverlay=max98357a
#dtoverlay=googlevoicehat-soundcard
#dtparam=audio=on

# Disable HDMI audio while using custom I2S audio
dtoverlay=vc4-kms-v3d,noaudio
```

Then reboot:

```bash
sudo reboot
```

## Expected ALSA Devices

After reboot:

```bash
aplay -l
arecord -l
cat /proc/asound/cards
python3 -m sounddevice
```

Expected map:

| Function | Device |
|---|---|
| Speaker playback | `hw:0,0` or `plughw:0,0` |
| Mic capture | `hw:0,1` |
| Python sounddevice playback | index 0, 0 in / 2 out |
| Python sounddevice capture | index 1, 8 in / 0 out |

Mic scripts should use `DEVICE = 1`.

Run the repository verifier:

```bash
bash raspberry_pi/audio/scripts/verify_combined_audio_setup.sh
```

## Speaker Test

```bash
python3 raspberry_pi/audio/scripts/audio_mode.py speak
speaker-test -D plughw:0,0 -c 2 -r 48000 -t sine -f 440
```

When the test is done:

```bash
python3 raspberry_pi/audio/scripts/audio_mode.py off
```

## Mic Test

```bash
python3 raspberry_pi/audio/scripts/audio_mode.py listen
arecord -D hw:0,1 -c 4 -r 48000 -f S32_LE -t wav -d 7 mic_test.wav
soxi mic_test.wav
```

Expected `soxi` result:

```text
Channels       : 4
Sample Rate    : 48000
Precision      : 32-bit
```

## 4-Mic Mapping Test

Package setup:

```bash
python3 -m venv ~/mic-test-venv
source ~/mic-test-venv/bin/activate
pip install -r requirements.txt
```

Run:

```bash
source ~/mic-test-venv/bin/activate
python3 raspberry_pi/audio/scripts/audio_mode.py listen
python3 raspberry_pi/audio/scripts/four_mic_new_mapping_test.py
```

The script prints RMS and dBFS per electrical channel. Use it to map the
electrical channels to physical directions after the mics are mounted.

## App-Level Flow

1. Wake/listening mode:

   ```bash
   python3 raspberry_pi/audio/scripts/audio_mode.py listen
   ```

   Amp is off, mics are on. Wake word, STT, and direction detection should use
   capture device index 1 or ALSA `hw:0,1`.

2. Before TTS:

   Close or stop the mic stream, then run:

   ```bash
   python3 raspberry_pi/audio/scripts/audio_mode.py speak
   ```

   Mics are off, amp is on. Play TTS to `plughw:0,0`.

3. After TTS:

   ```bash
   python3 raspberry_pi/audio/scripts/audio_mode.py listen
   ```

   Resume wake-word and mic capture.
