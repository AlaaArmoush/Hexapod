from __future__ import annotations

import time
from enum import Enum, auto

from bridge.robot_commands import build_gait, build_rotate


class ApproachResult(Enum):
    ARRIVED = auto()
    LOST = auto()
    TIMEOUT = auto()


class ApproachController:
    CLOSE_ENOUGH_M = 0.9      # metres — person is close enough to greet
    CENTER_THRESHOLD = 0.25   # |frame_position_x| below this counts as centred
    TIMEOUT_S = 60.0
    STEP_WAIT_S = 1.2         # wait for motion + a fresh tracker frame
    LOST_THRESHOLD_MS = 2000  # declare LOST after this many ms with no detection

    def __init__(self, tracker, cmd_fn) -> None:
        self._tracker = tracker
        self._cmd_fn = cmd_fn

    def run(self) -> ApproachResult:
        print(f"[approach] started, threshold={self.CLOSE_ENOUGH_M}m", flush=True)
        deadline = time.time() + self.TIMEOUT_S

        while time.time() < deadline:
            t = self._tracker.target

            if t is None:
                lost_ms = self._tracker.lost_ms
                print(f"[approach] no target (lost {lost_ms}ms)", flush=True)
                if lost_ms > self.LOST_THRESHOLD_MS:
                    print("[approach] → LOST", flush=True)
                    return ApproachResult.LOST
                time.sleep(0.1)
                continue

            depth_str = f"{t.distance_m:.2f}m" if t.distance_m is not None else "None"
            print(f"[approach] dist={depth_str}  x={t.frame_position_x:+.2f}  threshold={self.CLOSE_ENOUGH_M}m", flush=True)

            if t.distance_m is not None and t.distance_m <= self.CLOSE_ENOUGH_M:
                print(f"[approach] → ARRIVED ({t.distance_m:.2f}m <= {self.CLOSE_ENOUGH_M}m)", flush=True)
                return ApproachResult.ARRIVED

            if abs(t.frame_position_x) > self.CENTER_THRESHOLD:
                direction = "left" if t.frame_position_x < 0 else "right"
                print(f"[approach] rotating {direction} (x={t.frame_position_x:+.2f})", flush=True)
                self._cmd_fn(build_rotate(dir=direction, cycles=1))
            else:
                print("[approach] walking forward", flush=True)
                self._cmd_fn(build_gait(dir="forward", steps=3))

            time.sleep(self.STEP_WAIT_S)

        print("[approach] → TIMEOUT", flush=True)
        return ApproachResult.TIMEOUT

