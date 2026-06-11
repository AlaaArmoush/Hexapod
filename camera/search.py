from __future__ import annotations

import time
from dataclasses import dataclass

from bridge.robot_commands import build_camera_center, build_camera_pan


@dataclass
class SearchResult:
    found: bool
    position: str | None      # camera pan position where object was best seen
    confidence: float
    distance_m: float | None


class ObjectSearcher:
    SCAN_POSITIONS = ["left", "front_left", "center", "front_right", "right"]
    SETTLE_S = 0.5             # wait after each pan for frames to stabilise

    def __init__(self, provider, detector, cmd_fn) -> None:
        self._provider = provider
        self._detector = detector
        self._cmd_fn = cmd_fn

    def search(self, target_label: str) -> SearchResult:
        best_conf = 0.0
        best_pos = None
        best_dist = None

        for pos in self.SCAN_POSITIONS:
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
                    best_pos = pos
                    best_dist = best.distance_m

        self._cmd_fn(build_camera_center())

        return SearchResult(
            found=best_conf > 0.0,
            position=best_pos,
            confidence=round(best_conf, 3),
            distance_m=best_dist,
        )
