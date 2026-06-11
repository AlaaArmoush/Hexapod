from __future__ import annotations

import threading
import time
from dataclasses import dataclass

import numpy as np


@dataclass
class TrackedPerson:
    frame_position_x: float   # -1.0..+1.0, left→right
    frame_position_y: float   # -1.0..+1.0, top→bottom
    confidence: float
    distance_m: float | None  # None on host-detector path
    bbox_area: float          # normalized 0..1 — distance proxy when distance_m is None
    timestamp_ms: int


class PersonTracker:
    """Background thread that continuously detects the closest person.

    Uses distance_m when available (on-device path); falls back to
    largest bbox_area as a distance proxy (host path).
    """

    LOST_TIMEOUT_MS = 2000
    EMA_ALPHA = 0.4

    def __init__(self, provider, detector, *, fps: int = 5) -> None:
        self.provider = provider
        self.detector = detector
        self._interval = 1.0 / fps
        self._lock = threading.Lock()
        self._target: TrackedPerson | None = None
        self._last_seen_ms: int = 0
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    @property
    def target(self) -> TrackedPerson | None:
        with self._lock:
            return self._target

    @property
    def lost_ms(self) -> int:
        """Milliseconds since the person was last seen. 0 if currently tracked."""
        with self._lock:
            if self._target is None:
                return int(time.time() * 1000) - self._last_seen_ms if self._last_seen_ms else 0
            return 0

    def _loop(self) -> None:
        while self._running:
            t0 = time.time()
            try:
                self._tick()
            except Exception:
                pass
            elapsed = time.time() - t0
            remaining = self._interval - elapsed
            if remaining > 0:
                time.sleep(remaining)

    def _tick(self) -> None:
        now_ms = int(time.time() * 1000)
        frame = self.provider.grab_frame()
        depth = self.provider.grab_depth()
        result = self.detector.detect(frame, target_label="person") if frame is not None else None

        if result is None or not result.detected:
            with self._lock:
                if self._last_seen_ms and (now_ms - self._last_seen_ms) > self.LOST_TIMEOUT_MS:
                    self._target = None
            return

        best = self._pick_closest(result.detections)
        distance_m = best.distance_m if best.distance_m is not None else _sample_depth(depth, best.frame_position_x, best.frame_position_y)

        with self._lock:
            self._last_seen_ms = now_ms
            if self._target is None:
                self._target = TrackedPerson(
                    frame_position_x=best.frame_position_x,
                    frame_position_y=best.frame_position_y,
                    confidence=best.confidence,
                    distance_m=distance_m,
                    bbox_area=best.bbox_area,
                    timestamp_ms=now_ms,
                )
            else:
                a = self.EMA_ALPHA
                self._target = TrackedPerson(
                    frame_position_x=round(a * best.frame_position_x + (1 - a) * self._target.frame_position_x, 3),
                    frame_position_y=round(a * best.frame_position_y + (1 - a) * self._target.frame_position_y, 3),
                    confidence=best.confidence,
                    distance_m=distance_m,
                    bbox_area=best.bbox_area,
                    timestamp_ms=now_ms,
                )

    @staticmethod
    def _pick_closest(detections):
        """Prefer smallest distance_m; fall back to largest bbox_area."""
        with_depth = [d for d in detections if d.distance_m is not None]
        if with_depth:
            return min(with_depth, key=lambda d: d.distance_m)
        return max(detections, key=lambda d: d.bbox_area)


def _sample_depth(depth_frame, norm_x: float, norm_y: float) -> float | None:
    """Sample OAK-D depth (mm uint16) at a normalised position, return metres."""
    if depth_frame is None:
        return None
    h, w = depth_frame.shape[:2]
    px = max(0, min(w - 1, int((norm_x + 1) / 2 * w)))
    py = max(0, min(h - 1, int((norm_y + 1) / 2 * h)))
    patch = depth_frame[max(0, py - 4):py + 5, max(0, px - 4):px + 5]
    valid = patch[patch > 0]
    if len(valid) == 0:
        return None
    return round(float(valid.mean()) / 1000.0, 3)
