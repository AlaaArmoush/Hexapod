from __future__ import annotations

import numpy as np

# Electrical channel mapping (fixed — only physical labels change if mics are remounted):
# CH0 = GPIO20/pin38, L/R -> GND
# CH1 = GPIO20/pin38, L/R -> 3.3V
# CH2 = GPIO22/pin15, L/R -> GND
# CH3 = GPIO22/pin15, L/R -> 3.3V

# Physical direction per leading channel (verify with scripts/test_mic_energy.py):
_LEADER_TO_DIRECTION = {
    0: "front_left",   # CH0: pin38/GND
    1: "back_left",    # CH1: pin38/3V3
    2: "front_right",  # CH2: pin15/GND
    3: "back_right",   # CH3: pin15/3V3
}

_MIN_ADVANTAGE_DB = 3.0   # dB above runner-up to commit to a direction
_EPS = 1e-12


class DirectionEstimator:
    def estimate(self) -> str:
        raise NotImplementedError

    def update(self, multichannel_chunk: np.ndarray) -> None:
        raise NotImplementedError

    def reset(self) -> None:
        raise NotImplementedError


class RealDirectionEstimator(DirectionEstimator):
    """
    Accumulates per-channel energy across audio chunks (same approach as
    test_mic_energy.py), then on estimate() finds the leading mic and maps
    it to a direction string.
    """

    def __init__(self, min_advantage_db: float = _MIN_ADVANTAGE_DB) -> None:
        self._min_advantage_db = min_advantage_db
        self._energy = np.zeros(4, dtype=np.float64)
        self._sample_count = 0

    def update(self, multichannel_chunk: np.ndarray) -> None:
        """Accumulate squared energy from a 4-channel float32 chunk (shape: [frames, 4])."""
        x = multichannel_chunk[:, :4].astype(np.float64)
        self._energy += np.sum(x * x, axis=0)
        self._sample_count += x.shape[0]

    def estimate(self) -> str:
        if self._sample_count == 0:
            return "center"

        rms = np.sqrt(self._energy / self._sample_count)
        db = 20.0 * np.log10(np.maximum(rms, _EPS))

        leader = int(np.argmax(db))
        sorted_db = np.sort(db)
        advantage_db = sorted_db[-1] - sorted_db[-2]

        if advantage_db < self._min_advantage_db:
            return "center"

        direction = _LEADER_TO_DIRECTION[leader]

        # Collapse back_left / back_right → "back" (body rotate either way)
        if direction in ("back_left", "back_right"):
            return "back"
        return direction

    def reset(self) -> None:
        self._energy[:] = 0.0
        self._sample_count = 0
