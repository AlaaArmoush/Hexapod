#!/usr/bin/env bash
set -euo pipefail

OVERLAY_NAME="hexapod-4mic-max98357a"
WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DTS_FILE="$WORKDIR/overlays/${OVERLAY_NAME}.dts"
DTBO_FILE="/tmp/${OVERLAY_NAME}.dtbo"
CONFIG_FILE="/boot/firmware/config.txt"

if [[ ! -f "$DTS_FILE" ]]; then
  echo "Overlay source not found: $DTS_FILE" >&2
  exit 1
fi

echo "[1/5] Installing audio setup requirements..."
sudo apt update
sudo apt install -y \
  device-tree-compiler \
  alsa-utils \
  sox \
  python3 \
  python3-venv \
  python3-pip \
  libportaudio2

echo "[2/5] Compiling $OVERLAY_NAME..."
dtc -@ -I dts -O dtb -o "$DTBO_FILE" "$DTS_FILE"

echo "[3/5] Installing overlay to /boot/firmware/overlays..."
sudo cp "$DTBO_FILE" "/boot/firmware/overlays/${OVERLAY_NAME}.dtbo"

echo "[4/5] Backing up config.txt..."
sudo cp "$CONFIG_FILE" "${CONFIG_FILE}.backup_before_${OVERLAY_NAME}_$(date +%Y%m%d_%H%M%S)"

echo "[5/5] Next manual step:"
echo "Edit $CONFIG_FILE and use this audio section:"
echo
echo "dtparam=i2c_arm=on"
echo "dtparam=i2s=on"
echo "#dtparam=spi=on"
echo
echo "dtoverlay=${OVERLAY_NAME}"
echo
echo "# Disable old separate overlays"
echo "#dtoverlay=hexapod-4mic"
echo "#dtoverlay=max98357a"
echo "#dtoverlay=googlevoicehat-soundcard"
echo "#dtparam=audio=on"
echo
echo "# Disable HDMI audio while using custom I2S audio"
echo "dtoverlay=vc4-kms-v3d,noaudio"
echo
echo "Then reboot:"
echo "sudo reboot"
echo
echo "After reboot, verify with:"
echo "bash raspberry_pi/audio/scripts/verify_combined_audio_setup.sh"
