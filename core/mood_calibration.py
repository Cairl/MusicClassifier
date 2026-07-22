"""Personalized mood calibration.

Collects (model raw 1-9 score -> user-perceived VA) sample pairs and fits an
isotonic regression per dimension. Below MIN_SAMPLES the mapping falls back
to the default linear normalization (score - 5) / 4.
"""

import json
import os
import time
from dataclasses import asdict, dataclass

import numpy as np
from sklearn.isotonic import IsotonicRegression


@dataclass
class CalibrationSample:
    raw_valence: float
    raw_arousal: float
    user_valence: float
    user_arousal: float
    timestamp: float


class CalibrationStore:
    def __init__(self, path: str):
        self._path = path
        self.samples: list[CalibrationSample] = []
        self.load()

    def load(self) -> None:
        if not os.path.isfile(self._path):
            self.samples = []
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.samples = [CalibrationSample(**item) for item in data]
        except (json.JSONDecodeError, TypeError, KeyError):
            self.samples = []

    def save(self) -> None:
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump([asdict(s) for s in self.samples], f, ensure_ascii=False, indent=2)

    def add(self, sample: CalibrationSample) -> None:
        self.samples.append(sample)
        self.save()


class Calibrator:
    MIN_SAMPLES = 10

    def __init__(self, store: CalibrationStore):
        self._store = store
        self._v_model: IsotonicRegression | None = None
        self._a_model: IsotonicRegression | None = None
        self.refit()

    @property
    def active(self) -> bool:
        return self._v_model is not None and self._a_model is not None

    def refit(self) -> None:
        samples = self._store.samples
        if len(samples) < self.MIN_SAMPLES:
            self._v_model = None
            self._a_model = None
            return
        raw_v = np.array([s.raw_valence for s in samples])
        raw_a = np.array([s.raw_arousal for s in samples])
        user_v = np.array([s.user_valence for s in samples])
        user_a = np.array([s.user_arousal for s in samples])
        self._v_model = IsotonicRegression(out_of_bounds="clip").fit(raw_v, user_v)
        self._a_model = IsotonicRegression(out_of_bounds="clip").fit(raw_a, user_a)

    def calibrate(self, raw_valence: float, raw_arousal: float) -> tuple[float, float]:
        if not self.active:
            return (
                self._default_normalize(raw_valence),
                self._default_normalize(raw_arousal),
            )
        v = float(self._v_model.predict([raw_valence])[0])
        a = float(self._a_model.predict([raw_arousal])[0])
        return (
            max(-1.0, min(1.0, v)),
            max(-1.0, min(1.0, a)),
        )

    @staticmethod
    def _default_normalize(score: float) -> float:
        score = max(1.0, min(9.0, score))
        return (score - 5.0) / 4.0
