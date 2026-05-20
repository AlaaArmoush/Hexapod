#!/usr/bin/env bash
set -euo pipefail

echo "=== OS ==="
cat /etc/os-release | head -5 || true
echo

echo "=== Audio config ==="
grep -nE "i2s|googlevoice|hexapod|audio" /boot/firmware/config.txt || true
echo

echo "=== Capture devices ==="
arecord -l
echo

echo "=== ALSA cards ==="
cat /proc/asound/cards
echo

echo "=== Kernel modules ==="
lsmod | grep -iE "dmic|simple|snd_soc|designware" || true
echo

echo "=== Pinmux ==="
pinctrl get 18
pinctrl get 19
pinctrl get 20
pinctrl get 21
pinctrl get 22
echo

echo "=== Hardware params test ==="
arecord -D hw:2,0 --dump-hw-params -c 4 -r 48000 -f S32_LE -d 1 /tmp/four_hw_test.wav || true