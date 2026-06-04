# Raspberry Pi Audio Assets

This directory holds the Raspberry Pi 5 audio files that are installed or run
on the robot.

The current setup is a combined I2S0 bus:

- 4x INMP441 microphones for capture.
- 1x MAX98357A amplifier/speaker for playback.
- GPIO17 controls switched microphone power.
- GPIO27 controls the MAX98357A SD/mute pin.

Keep Device Tree sources in `overlays/` even while there is only one overlay;
it keeps boot-time audio hardware descriptions separate from runtime scripts.

The canonical setup and wiring guide lives at:

```text
docs/RASPBERRY_PI_AUDIO_SETUP.md
```

Python dependencies for the mic mapping test are listed in the project-level:

```text
requirements.txt
```

`raspberry_pi/docs/` is intentionally not used for this audio setup anymore so
there is only one maintained guide.
