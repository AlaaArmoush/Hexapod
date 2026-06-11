from __future__ import annotations

from collections import deque

import numpy as np

# Electrical channel mapping (fixed — only physical labels change if mics are remounted):
# CH0 = GPIO22/pin15, L/R -> GND  → FRONT
# CH1 = GPIO22/pin15, L/R -> 3.3V → RIGHT
# CH2 = GPIO20/pin38, L/R -> GND  → LEFT
# CH3 = GPIO20/pin38, L/R -> 3.3V → BACK

_LEADER_TO_DIRECTION = {
    0: "front",  # CH0: pin15/GND
    1: "right",  # CH1: pin15/3V3
    2: "left",   # CH2: pin38/GND
    3: "back",   # CH3: pin38/3V3
}

_MIN_ADVANTAGE_DB = 1.0   # dB above runner-up to commit to a direction
_EPS = 1e-12


class DirectionEstimator:
    def estimate(self) -> str:
        raise NotImplementedError

    def update(self, multichannel_chunk: np.ndarray) -> None:
        raise NotImplementedError

    def reset(self) -> None:
        raise NotImplementedError


class RealDirectionEstimator(DirectionEstimator):
    def __init__(
        self,
        min_advantage_db: float = _MIN_ADVANTAGE_DB,
        window_chunks: int = 18,  # 18 × 80 ms ≈ 1.44 s at 48 kHz / 3840-frame chunks
    ) -> None:
        self._min_advantage_db = min_advantage_db
        self._chunks: deque[tuple[np.ndarray, int]] = deque(maxlen=window_chunks)

    def update(self, multichannel_chunk: np.ndarray) -> None:
        x = multichannel_chunk[:, :4].astype(np.float64)
        self._chunks.append((np.sum(x * x, axis=0), x.shape[0]))

    def estimate(self) -> str:
        if not self._chunks:
            return "center"

        total_energy = sum(e for e, _ in self._chunks)
        total_samples = sum(n for _, n in self._chunks)

        rms = np.sqrt(total_energy / total_samples)
        db = 20.0 * np.log10(np.maximum(rms, _EPS))

        leader = int(np.argmax(db))
        sorted_db = np.sort(db)
        if sorted_db[-1] - sorted_db[-2] < self._min_advantage_db:
            # No clear winner — use loudest channel anyway rather than center
            pass

        return _LEADER_TO_DIRECTION[leader]

    def reset(self) -> None:
        self._chunks.clear()
