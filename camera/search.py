from __future__ import annotations

import time
from dataclasses import dataclass

from bridge.robot_commands import build_camera_center, build_camera_pan, build_rotate


@dataclass
class SearchResult:
    found: bool
    position: str | None      # describes where the object was found
    confidence: float
    distance_m: float | None


# Body orientations (degrees rotated from start, cumulative).  6 × 60° = full circle.
_BODY_ROTATIONS = [0, 60, 60, 60, 60, 60]
_CAMERA_POSITIONS = ["left", "center", "right"]


class ObjectSearcher:
    SETTLE_S = 0.4   # wait after each pan for frames to stabilise
    ROTATE_WAIT_S = 1.5   # wait after each body rotation for tracker to settle

    def __init__(self, provider, detector, cmd_fn) -> None:
        self._provider = provider
        self._detector = detector
        self._cmd_fn = cmd_fn

    def _scan_at_current_orientation(self, target_label: str) -> tuple[float, float | None]:
        best_conf = 0.0
        best_dist = None
        for pos in _CAMERA_POSITIONS:
            self._cmd_fn(build_camera_pan(pos=pos))
            time.sleep(self.SETTLE_S)
            frame = self._provider.grab_frame()
            if frame is None:
                continue
            result = self._detector.detect(frame, target_label=target_label)
            if result.detected:
                best = max(result.detections, key=lambda d: d.confidence)
                if best.confidence > best_conf:
                    best_conf = best.confidence
                    best_dist = best.distance_m
        self._cmd_fn(build_camera_center())
        return best_conf, best_dist

    def search(self, target_label: str) -> SearchResult:
        best_conf = 0.0
        best_orientation = 0   # degrees rotated from start when best seen
        best_dist = None
        total_rotated = 0

        for i, degrees in enumerate(_BODY_ROTATIONS):
            if degrees > 0:
                self._cmd_fn(build_rotate(dir="left", degrees=degrees))
                total_rotated += degrees
                time.sleep(self.ROTATE_WAIT_S)

            conf, dist = self._scan_at_current_orientation(target_label)
            if conf > best_conf:
                best_conf = conf
                best_orientation = total_rotated
                best_dist = dist
            if best_conf > 0.5:   # confident enough — stop early
                break

        # Rotate back to face the direction where the object was best seen.
        # We've rotated total_rotated degrees left total; undo back to best_orientation.
        undo = total_rotated - best_orientation
        if undo > 0:
            self._cmd_fn(build_rotate(dir="right", degrees=undo))
            time.sleep(self.ROTATE_WAIT_S)

        found = best_conf > 0.0
        position = (f"{best_orientation}° to my left" if best_orientation > 0 else "right in front of me") if found else None

        return SearchResult(
            found=found,
            position=position,
            confidence=round(best_conf, 3),
            distance_m=best_dist,
        )
