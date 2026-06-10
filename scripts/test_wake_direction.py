"""
Standalone test: wake word + direction detection + camera pan / body rotate.

Usage:
    python scripts/test_wake_direction.py                        # dry-run, no robot
    python scripts/test_wake_direction.py --port /dev/ttyUSB0   # real hardware
    python scripts/test_wake_direction.py --threshold 0.2        # lower sensitivity
    python scripts/test_wake_direction.py --debug                # print live scores
"""
from __future__ import annotations

import argparse
import queue
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bridge.robot_commands import build_camera_pan, build_rotate
from raspberry_pi.audio.scripts.audio_mode import listen as audio_listen, off as audio_off
from raspberry_pi.wake_word.detector import WakeWordDetector
from raspberry_pi.wake_word.pipeline import WAKEWORD_MODEL_PATH, WAKEWORD_THRESHOLD, AUDIO_DEVICE

COOLDOWN_SECS = 2.0


def direction_to_commands(direction: str) -> list[dict]:
    if direction == "back":
        return [build_rotate(dir="left", degrees=180), build_camera_pan("center")]
    pan_pos = direction if direction not in ("front", "center") else "center"
    return [build_camera_pan(pan_pos)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", help="Serial port, e.g. /dev/ttyUSB0. Omit for dry-run.")
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--threshold", type=float, default=WAKEWORD_THRESHOLD)
    parser.add_argument("--debug", action="store_true", help="Print live wake word scores.")
    args = parser.parse_args()

    dry_run = args.port is None
    bridge = None

    if not dry_run:
        from bridge.serial_robot_bridge import SerialRobotBridge
        bridge = SerialRobotBridge(port=args.port, baudrate=args.baudrate)
        bridge.connect()
        time.sleep(3.0)  # wait for ESP32 to finish booting
        while bridge._serial.in_waiting:  # drain boot messages without toggling DTR
            bridge._serial.read(bridge._serial.in_waiting)
            time.sleep(0.05)
        print(f"[test] connected to {args.port}", file=sys.stderr)
    else:
        print("[test] dry-run mode", file=sys.stderr)

    audio_listen()

    event_queue: queue.Queue[tuple[str, float, str]] = queue.Queue()
    last_time: list[float] = [0.0]

    def on_wakeword(model_name: str, score: float, direction: str) -> None:
        now = time.monotonic()
        if now - last_time[0] < COOLDOWN_SECS:
            return
        last_time[0] = now
        event_queue.put_nowait((model_name, score, direction))

    detector = WakeWordDetector(
        model_path=WAKEWORD_MODEL_PATH,
        on_wakeword=on_wakeword,
        threshold=args.threshold,
        device=AUDIO_DEVICE,
        debug=args.debug,
    )
    detector.start()
    print(f"[test] listening — say 'Hey Heksah'  (threshold={args.threshold})", file=sys.stderr)

    try:
        while True:
            try:
                model_name, score, direction = event_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            cmds = direction_to_commands(direction)
            print(f"\n[test] score={score:.3f}  direction={direction!r}  "
                  f"→ {[c['cmd'] + ' ' + str(c.get('pos', c.get('dir', ''))) for c in cmds]}",
                  file=sys.stderr)

            if dry_run:
                for cmd in cmds:
                    print(f"[test] DRY-RUN: {cmd}", file=sys.stderr)
            else:
                for cmd in cmds:
                    try:
                        print(f"[test] sending: {cmd}", file=sys.stderr)
                        bridge.send_command(cmd)
                        resp = bridge.wait_for_ok(cmd=cmd["cmd"], timeout=8.0)
                        print(f"[test] ok: {resp['raw']}", file=sys.stderr)
                    except Exception as exc:
                        print(f"[test] error: {exc}", file=sys.stderr)

    except KeyboardInterrupt:
        print("\n[test] stopping", file=sys.stderr)
    finally:
        detector.stop()
        audio_off()
        if bridge is not None:
            bridge.close()


if __name__ == "__main__":
    main()
