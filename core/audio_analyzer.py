import threading
from collections import deque
from dataclasses import dataclass

import librosa
import numpy as np
from PySide6.QtCore import QObject, Signal

from core.audio_capture import AudioCaptureManager


@dataclass
class MoodCoordinates:
    arousal: float
    valence: float
    quadrant: str
    confidence: float


class AnalyzerSignals(QObject):
    mood_analyzed = Signal(float, float, str, float)
    analysis_error = Signal(str)


class AudioAnalyzer:
    ANALYSIS_INTERVAL = 2.0
    SNAPSHOT_SECONDS = 5.0
    HISTORY_SIZE = 5

    def __init__(self, capture_manager: AudioCaptureManager):
        self._capture = capture_manager
        self._running = False
        self._thread: threading.Thread | None = None
        self._signals = AnalyzerSignals()
        self._recent_quadrants: deque[str] = deque(maxlen=self.HISTORY_SIZE)
        self._current_confidence: float = 0.0

    @property
    def signals(self) -> AnalyzerSignals:
        return self._signals

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._recent_quadrants.clear()
        self._current_confidence = 0.0
        self._thread = threading.Thread(target=self._analysis_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None

    def _analysis_loop(self) -> None:
        while self._running:
            try:
                audio = self._capture.get_snapshot(self.SNAPSHOT_SECONDS)
                if audio is not None:
                    mono = np.mean(audio, axis=0).astype(np.float32)
                    result = self._analyze_chunk(mono, 48000)
                    self._recent_quadrants.append(result.quadrant)
                    result.confidence = self._compute_confidence()
                    self._current_confidence = result.confidence
                    self._signals.mood_analyzed.emit(
                        result.arousal, result.valence,
                        result.quadrant, result.confidence
                    )
            except Exception as e:
                self._signals.analysis_error.emit(str(e))

            event = threading.Event()
            event.wait(timeout=self.ANALYSIS_INTERVAL)

    def _analyze_chunk(self, audio: np.ndarray, sr: int) -> MoodCoordinates:
        features = self._extract_features(audio, sr)
        return self._map_to_quadrant(features)

    def _extract_features(self, audio: np.ndarray, sr: int) -> dict:
        rms = librosa.feature.rms(y=audio)[0]
        rms_val = float(np.mean(rms))

        centroid = librosa.feature.spectral_centroid(y=audio, sr=sr)[0]
        centroid_val = float(np.mean(centroid))

        zcr = librosa.feature.zero_crossing_rate(y=audio)[0]
        zcr_val = float(np.mean(zcr))

        bandwidth = librosa.feature.spectral_bandwidth(y=audio, sr=sr)[0]
        bandwidth_val = float(np.mean(bandwidth))

        tempo, _ = librosa.beat.beat_track(y=audio, sr=sr)
        tempo_val = float(tempo) if np.isscalar(tempo) else float(tempo[0])

        harmonic = librosa.effects.harmonic(y=audio)
        harmonic_ratio = float(np.mean(np.abs(harmonic)) / (np.mean(np.abs(audio)) + 1e-10))

        return {
            "rms_norm": min(rms_val / 0.1, 1.0),
            "tempo_norm": min(max((tempo_val - 60) / 160, 0.0), 1.0),
            "bandwidth_norm": min(bandwidth_val / 6000.0, 1.0),
            "centroid_norm": min(centroid_val / 6000.0, 1.0),
            "zcr_norm": min(zcr_val / 0.15, 1.0),
            "harmonic_ratio": min(harmonic_ratio / 1.5, 1.0),
        }

    def _map_to_quadrant(self, features: dict) -> MoodCoordinates:
        arousal_raw = (
            features["rms_norm"] * 0.4
            + features["tempo_norm"] * 0.3
            + features["bandwidth_norm"] * 0.3
        )
        valence_raw = (
            features["centroid_norm"] * 0.5
            - features["zcr_norm"] * 0.3
            + features["harmonic_ratio"] * 0.2
        )

        arousal = max(-1.0, min(1.0, arousal_raw * 2 - 1))
        valence = max(-1.0, min(1.0, (valence_raw - 0.2) / 0.5))

        if arousal >= 0 and valence >= 0:
            quadrant = "VIGOROUS"
        elif arousal >= 0 and valence < 0:
            quadrant = "TENSE"
        elif arousal < 0 and valence < 0:
            quadrant = "MELANCHOLY"
        else:
            quadrant = "CALM"

        return MoodCoordinates(
            arousal=arousal,
            valence=valence,
            quadrant=quadrant,
            confidence=0.0
        )

    def _compute_confidence(self) -> float:
        if not self._recent_quadrants:
            return 0.0
        most_common = max(set(self._recent_quadrants), key=list(self._recent_quadrants).count)
        count = list(self._recent_quadrants).count(most_common)
        return count / len(self._recent_quadrants)
