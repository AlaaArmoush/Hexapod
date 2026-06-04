#!/usr/bin/env bash
set -euo pipefail

echo "=== OS ==="
cat /etc/os-release | head -5 || true
echo

echo "=== Audio config ==="
grep -nE "i2s|googlevoice|hexapod|max98357a|audio|vc4-kms" /boot/firmware/config.txt || true
echo

echo "=== Playback devices ==="
aplay -l || true
echo

echo "=== Capture devices ==="
arecord -l || true
echo

echo "=== ALSA cards ==="
cat /proc/asound/cards || true
echo

echo "=== Python sounddevice map ==="
python3 -m sounddevice || true
echo

echo "=== Kernel modules ==="
lsmod | grep -iE "dmic|max98357a|simple|snd_soc|designware" || true
echo

echo "=== Pinmux ==="
pinctrl get 17 || true
pinctrl get 18 || true
pinctrl get 19 || true
pinctrl get 20 || true
pinctrl get 21 || true
pinctrl get 22 || true
pinctrl get 27 || true
echo

echo "=== Expected devices ==="
echo "speaker playback: hw:0,0 or plughw:0,0"
echo "mic capture:      hw:0,1"
echo "sounddevice:      index 0 playback, index 1 capture"
echo

echo "=== Capture hardware params smoke test ==="
arecord -D hw:0,1 --dump-hw-params -c 4 -r 48000 -f S32_LE -d 1 /tmp/hexapod_mic_hw_test.wav || true
echo

echo "=== Recommended mode commands ==="
echo "listen: python3 raspberry_pi/audio/scripts/audio_mode.py listen"
echo "speak:  python3 raspberry_pi/audio/scripts/audio_mode.py speak"
echo "off:    python3 raspberry_pi/audio/scripts/audio_mode.py off"
echo
echo "Raw pinctrl equivalents:"
echo "listen: sudo pinctrl set 27 op dl && sudo pinctrl set 17 op dl"
echo "speak:  sudo pinctrl set 17 op dh && sudo pinctrl set 27 op dh"
echo "off:    sudo pinctrl set 27 op dl && sudo pinctrl set 17 op dh"
