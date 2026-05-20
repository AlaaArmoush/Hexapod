# Raspberry Pi 5 — 4x INMP441 I2S Microphone Array Setup

This document explains how we configured a Raspberry Pi 5 to capture audio from **4x INMP441 I2S microphones** using a custom Device Tree overlay.

The setup was tested on a Raspberry Pi 5 with a DFRobot UPS HAT.

---

## 1. Important Hardware Notes

The UPS HAT occupies these Raspberry Pi physical pins:

```text
3, 5, 25, 31, 36
```

Avoid using those pins.

The 4-mic array uses these Raspberry Pi pins:

```text
Pin 12 = GPIO18 = I2S0_SCLK / BCLK
Pin 35 = GPIO19 = I2S0_WS / LRCLK
Pin 38 = GPIO20 = I2S0_SDI0
Pin 15 = GPIO22 = I2S0_SDI1
```

These do not conflict with the UPS HAT.

---

## 2. Microphone Wiring

All 4 INMP441 microphones share:

| INMP441 Pin | Raspberry Pi 5 |
|---|---|
| VDD | 3.3V |
| GND | GND |
| SCK | GPIO18 / physical pin 12 |
| WS | GPIO19 / physical pin 35 |

### Pair 1

| Mic | SD | L/R |
|---|---|---|
| Mic 1 | GPIO20 / physical pin 38 | GND |
| Mic 2 | GPIO20 / physical pin 38 | 3.3V |

### Pair 2

| Mic | SD | L/R |
|---|---|---|
| Mic 3 | GPIO22 / physical pin 15 | GND |
| Mic 4 | GPIO22 / physical pin 15 | 3.3V |

Expected channel mapping:

```text
CH0 = Pair 1 left  = GPIO20, L/R to GND
CH1 = Pair 1 right = GPIO20, L/R to 3.3V
CH2 = Pair 2 left  = GPIO22, L/R to GND
CH3 = Pair 2 right = GPIO22, L/R to 3.3V
```

---

## 3. Why the Stock Overlay Was Not Enough

The stock overlay:

```ini
dtoverlay=googlevoicehat-soundcard
```

worked for 2 microphones only.

It exposed only a 2-channel hardware device:

```text
CHANNELS: 2
```

Even after requesting 4 channels through `plughw`, channels 2 and 3 were zero.

The issue was that the default Pi 5 I2S0 pin group only used:

```text
GPIO18, GPIO19, GPIO20, GPIO21
```

So GPIO22 was not initially active as an I2S input.

We solved this by creating a custom overlay using:

```text
simple-audio-card
dmic-codec
RP1 I2S0
```

---

## 4. Custom Overlay File


```dts
/dts-v1/;
/plugin/;

/ {
    compatible = "brcm,bcm2712";

    /*
     * Hexapod 4x INMP441 microphone array for Raspberry Pi 5.
     *
     * Wiring:
     *   GPIO18 / pin 12 = I2S0_SCLK / BCLK
     *   GPIO19 / pin 35 = I2S0_WS / LRCLK
     *   GPIO20 / pin 38 = I2S0_SDI0 -> pair 1 left/right
     *   GPIO22 / pin 15 = I2S0_SDI1 -> pair 2 left/right
     *
     * GPIO21 is kept in the I2S0 group as SDO0 for possible future I2S output.
     */

    fragment@0 {
        target = <&rp1_i2s0_18_21>;
        __overlay__ {
            function = "i2s0";
            pins = "gpio18", "gpio19", "gpio20", "gpio21", "gpio22";
            bias-disable;
        };
    };

    fragment@1 {
        target = <&i2s_clk_producer>;
        __overlay__ {
            status = "okay";
        };
    };

    fragment@2 {
        target-path = "/";
        __overlay__ {
            hexapod_4mic_codec: hexapod-4mic-codec {
                compatible = "dmic-codec";
                #sound-dai-cells = <0>;
                status = "okay";
            };

            hexapod_4mic_soundcard: hexapod-4mic-soundcard {
                compatible = "simple-audio-card";
                simple-audio-card,name = "hexapod-4mic";
                simple-audio-card,format = "i2s";
                status = "okay";

                simple-audio-card,cpu {
                    sound-dai = <&i2s_clk_producer>;
                };

                simple-audio-card,codec {
                    sound-dai = <&hexapod_4mic_codec>;
                };
            };
        };
    };
};
```

---

## 5. Compile and Install Overlay

Install the compiler:

```bash
sudo apt update
sudo apt install -y device-tree-compiler
```

Compile:

```bash
dtc -@ -I dts -O dtb \
  -o hexapod-4mic.dtbo \
  hexapod-4mic.dts
```

Install:

```bash
sudo cp hexapod-4mic.dtbo /boot/firmware/overlays/
```

---

## 6. Update `/boot/firmware/config.txt`

Back up config first:

```bash
sudo cp /boot/firmware/config.txt /boot/firmware/config.txt.backup_before_4mic
```

Edit:

```bash
sudo nano /boot/firmware/config.txt
```

Use this audio section:

```ini
dtparam=i2s=on
#dtoverlay=googlevoicehat-soundcard
dtoverlay=hexapod-4mic
dtparam=audio=on
```

Reboot:

```bash
sudo reboot
```

---

## 7. Verify the Card

After reboot:

```bash
arecord -l
cat /proc/asound/cards
```

Expected:

```text
card 2: hexapod4mic [hexapod-4mic]
```

Check modules:

```bash
lsmod | grep -iE "dmic|simple|snd_soc|designware"
```

Expected modules include:

```text
snd_soc_simple_card
snd_soc_dmic
designware_i2s
```

Check pinmux:

```bash
pinctrl get 18
pinctrl get 19
pinctrl get 20
pinctrl get 21
pinctrl get 22
```

Expected:

```text
GPIO18 = I2S0_SCLK
GPIO19 = I2S0_WS
GPIO20 = I2S0_SDI0
GPIO21 = I2S0_SDO0
GPIO22 = I2S0_SDI1
```

---

## 8. Record 10-Second 4-Mic Test

```bash
arecord -D hw:2,0 -c 4 -r 48000 -f S32_LE -t wav -d 10 four_mic_10sec.wav
```

Check file:

```bash
soxi four_mic_10sec.wav
```

Expected:

```text
Channels       : 4
Sample Rate    : 48000
Precision      : 32-bit
```

---

## 9. Live Direction Test Script

Create:

```bash
nano four_mic_live_direction.py
```

Paste:

```python
import time
import numpy as np
import sounddevice as sd

SAMPLE_RATE = 48000
BLOCK_SIZE = 2048
CHANNELS = 4
PRINT_EVERY_SECONDS = 2.0
EPS = 1e-12

MIC_NAMES = [
    "CH0_PAIR1_LEFT",
    "CH1_PAIR1_RIGHT",
    "CH2_PAIR2_LEFT",
    "CH3_PAIR2_RIGHT",
]

DEVICE = None

energy = np.zeros(CHANNELS, dtype=np.float64)
sample_count = 0
last_print = time.time()


def rms_to_dbfs(rms: float) -> float:
    return 20.0 * np.log10(max(float(rms), EPS))


def make_bar(dbfs: float, min_db: float = -70.0, max_db: float = -20.0, width: int = 24) -> str:
    dbfs = max(min_db, min(max_db, dbfs))
    filled = int((dbfs - min_db) / (max_db - min_db) * width)
    return "█" * filled + "-" * (width - filled)


def callback(indata, frames, time_info, status):
    global energy, sample_count, last_print

    if status:
        print(f"[Audio status] {status}")

    if indata.shape[1] < CHANNELS:
        print(f"ERROR: expected {CHANNELS} channels, got {indata.shape[1]}")
        return

    x = indata[:, :CHANNELS].astype(np.float64)

    energy += np.sum(x * x, axis=0)
    sample_count += x.shape[0]

    now = time.time()
    if now - last_print >= PRINT_EVERY_SECONDS:
        rms = np.sqrt(energy / max(sample_count, 1))
        db = np.array([rms_to_dbfs(v) for v in rms])

        leader = int(np.argmax(db))
        sorted_db = np.sort(db)
        advantage_db = sorted_db[-1] - sorted_db[-2]

        if advantage_db < 3.0:
            direction = "UNCERTAIN"
        else:
            direction = MIC_NAMES[leader]

        print()
        print(f"Leading direction: {direction} | lead advantage: {advantage_db:.1f} dB")

        for i in range(CHANNELS):
            marker = "<-- LEADER" if i == leader and advantage_db >= 3.0 else ""
            print(
                f"  CH{i} {MIC_NAMES[i]:18} "
                f"RMS={rms[i]:.6f}  "
                f"dBFS={db[i]:7.1f}  "
                f"{make_bar(db[i])} {marker}"
            )

        print("-" * 90)

        energy[:] = 0.0
        sample_count = 0
        last_print = now


def main():
    print("Available devices:")
    print(sd.query_devices())
    print()
    print("Listening with 4 mics. Updates every 2 seconds. Ctrl+C to stop.")
    print("Expected mapping:")
    print("  CH0 = pair 1 left  / GPIO20 left slot")
    print("  CH1 = pair 1 right / GPIO20 right slot")
    print("  CH2 = pair 2 left  / GPIO22 left slot")
    print("  CH3 = pair 2 right / GPIO22 right slot")
    print()

    with sd.InputStream(
        device=DEVICE,
        channels=CHANNELS,
        samplerate=SAMPLE_RATE,
        blocksize=BLOCK_SIZE,
        dtype="float32",
        callback=callback,
    ):
        while True:
            sd.sleep(1000)


if __name__ == "__main__":
    main()
```

Run:

```bash
source ~/mic-test-venv/bin/activate
python3 four_mic_live_direction.py
```

Expected: all 4 channels should show nonzero RMS values.

---

## 10. Rollback

If the custom overlay breaks audio:

```bash
sudo cp /boot/firmware/config.txt.backup_before_4mic /boot/firmware/config.txt
sudo reboot
```

Or manually edit:

```bash
sudo nano /boot/firmware/config.txt
```

Disable:

```ini
#dtoverlay=hexapod-4mic
```

And restore 2-mic overlay if needed:

```ini
dtoverlay=googlevoicehat-soundcard
```