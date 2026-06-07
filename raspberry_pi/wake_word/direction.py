from __future__ import annotations

import numpy as np


class DirectionEstimator:
    def estimate(self, audio_chunk: np.ndarray) -> str:
        raise NotImplementedError


class RealDirectionEstimator(DirectionEstimator):
    """
    Uses per-channel RMS energy to pick a horizontal direction.
    """

    def __init__(self, min_advantage_db: float = 3.0, history: int = 5) -> None:
        self._min_advantage_db = min_advantage_db
        self._history = history
        self._energy_left: list[float] = []
        self._energy_right: list[float] = []

    def _rms(self, signal: np.ndarray) -> float:
        return float(np.sqrt(np.mean(signal.astype(np.float64) ** 2)) + 1e-10)

    def update(self, multichannel_chunk: np.ndarray) -> None:
        """Accumulate energy from a 4-channel chunk (shape: [frames, 4])."""
        left = (self._rms(multichannel_chunk[:, 0]) + self._rms(multichannel_chunk[:, 1])) / 2
        right = (self._rms(multichannel_chunk[:, 2]) + self._rms(multichannel_chunk[:, 3])) / 2
        self._energy_left.append(left)
        self._energy_right.append(right)
        if len(self._energy_left) > self._history:
            self._energy_left.pop(0)
            self._energy_right.pop(0)

    def estimate(self, audio_chunk: np.ndarray) -> str:
        """Return 'left', 'right', or 'center' based on accumulated energy."""
        if not self._energy_left:
            return "center"
        avg_left = sum(self._energy_left) / len(self._energy_left)
        avg_right = sum(self._energy_right) / len(self._energy_right)
        db_diff = 20 * np.log10((avg_left + 1e-10) / (avg_right + 1e-10))
        if db_diff > self._min_advantage_db:
            return "left"
        if db_diff < -self._min_advantage_db:
            return "right"
        return "center"

    def reset(self) -> None:
        self._energy_left.clear()
        self._energy_right.clear()


# [MOCK - will be deleted]
class MockDirectionEstimator(DirectionEstimator):
    """Cycles through directions so the full pipeline can be tested on a laptop."""

    _CYCLE = ["left", "center", "right", "center"]

    def __init__(self) -> None:
        self._idx = 0

    def estimate(self, audio_chunk: np.ndarray) -> str:
        direction = self._CYCLE[self._idx % len(self._CYCLE)]
        self._idx += 1
        return direction

    def reset(self) -> None:
        pass  # cycle index intentionally preserved between detections


# [MOCK]
def make_direction_estimator(use_mock: bool = False) -> DirectionEstimator:
    if use_mock:
        return MockDirectionEstimator()
    return RealDirectionEstimator()
