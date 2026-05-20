#!/usr/bin/env bash
set -euo pipefail

OVERLAY_NAME="hexapod-4mic"
WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DTS_FILE="$WORKDIR/overlays/${OVERLAY_NAME}.dts"
DTBO_FILE="/tmp/${OVERLAY_NAME}.dtbo"

echo "[1/5] Installing dependencies..."
sudo apt update
sudo apt install -y device-tree-compiler

echo "[2/5] Compiling overlay..."
dtc -@ -I dts -O dtb -o "$DTBO_FILE" "$DTS_FILE"

echo "[3/5] Installing overlay to /boot/firmware/overlays..."
sudo cp "$DTBO_FILE" "/boot/firmware/overlays/${OVERLAY_NAME}.dtbo"

echo "[4/5] Backing up config.txt..."
sudo cp /boot/firmware/config.txt "/boot/firmware/config.txt.backup_before_${OVERLAY_NAME}_$(date +%Y%m%d_%H%M%S)"

echo "[5/5] Next manual step:"
echo "Edit /boot/firmware/config.txt and use:"
echo
echo "dtparam=i2s=on"
echo "#dtoverlay=googlevoicehat-soundcard"
echo "dtoverlay=hexapod-4mic"
echo
echo "Then reboot:"
echo "sudo reboot"