from __future__ import annotations

import numpy as np


class DirectionEstimator:
    def estimate(self) -> str:
        raise NotImplementedError

    def update(self, multichannel_chunk: np.ndarray) -> None:
        raise NotImplementedError

    def reset(self) -> None:
        raise NotImplementedError


class RealDirectionEstimator(DirectionEstimator):
    """
    Uses per-channel RMS energy to estimate horizontal + front/back direction.

    Physical mic layout (4x INMP441):
        FRONT
        CH1 (3V3) ●    ● CH3 (3V3)
        CH0 (GND) ●    ● CH2 (GND)
        BACK

    Left  = CH0 + CH1,  Right = CH2 + CH3
    Front = CH0 + CH2,  Back  = CH1 + CH3

    Returns one of: "left", "front_left", "front", "front_right", "right", "back", "center"
    """

    def __init__(self, min_advantage_db: float = 3.0, history: int = 5) -> None:
        self._min_advantage_db = min_advantage_db
        self._history = history
        self._energy_left: list[float] = []
        self._energy_right: list[float] = []
        self._energy_front: list[float] = []
        self._energy_back: list[float] = []

    def _rms(self, signal: np.ndarray) -> float:
        return float(np.sqrt(np.mean(signal.astype(np.float64) ** 2)) + 1e-10)

    def update(self, multichannel_chunk: np.ndarray) -> None:
        """Accumulate energy from a 4-channel chunk (shape: [frames, 4])."""
        ch0, ch1, ch2, ch3 = (multichannel_chunk[:, i] for i in range(4))
        left  = (self._rms(ch0) + self._rms(ch1)) / 2
        right = (self._rms(ch2) + self._rms(ch3)) / 2
        front = (self._rms(ch0) + self._rms(ch2)) / 2
        back  = (self._rms(ch1) + self._rms(ch3)) / 2
        for lst, val in (
            (self._energy_left,  left),
            (self._energy_right, right),
            (self._energy_front, front),
            (self._energy_back,  back),
        ):
            lst.append(val)
            if len(lst) > self._history:
                lst.pop(0)

    def estimate(self) -> str:
        """Return direction string based on accumulated energy."""
        if not self._energy_left:
            return "center"

        def avg(lst: list[float]) -> float:
            return sum(lst) / len(lst)

        def db(a: float, b: float) -> float:
            return 20 * float(np.log10((a + 1e-10) / (b + 1e-10)))

        lr_db = db(avg(self._energy_left), avg(self._energy_right))
        fb_db = db(avg(self._energy_front), avg(self._energy_back))

        is_left  = lr_db >  self._min_advantage_db
        is_right = lr_db < -self._min_advantage_db
        is_front = fb_db >  self._min_advantage_db
        is_back  = fb_db < -self._min_advantage_db

        if is_back:
            return "back"
        if is_front:
            if is_left:  return "front_left"
            if is_right: return "front_right"
            return "front"
        if is_left:  return "left"
        if is_right: return "right"
        return "center"

    def reset(self) -> None:
        self._energy_left.clear()
        self._energy_right.clear()
        self._energy_front.clear()
        self._energy_back.clear()
