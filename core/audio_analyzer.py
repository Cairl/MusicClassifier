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
    boundary_detected = Signal()
    no_audio = Signal()


class AudioAnalyzer:
    ANALYSIS_INTERVAL = 3.0
    SNAPSHOT_SECONDS = 15.0
    WARMUP_START = 5.0
    WARMUP_STEP = 2.0
    HISTORY_SIZE = 7
    BOUNDARY_THRESHOLD = 0.8
    BOUNDARY_THRESHOLD_LOCKED = 1.2
    STABILIZATION_COUNT = 4
    COORD_HISTORY = 5
    LOCK_CONFIDENCE = 0.6
    SILENCE_RMS_THRESHOLD = 0.008

    FEATURE_EMA_ALPHA = 0.35
    FEATURE_BUFFER_SIZE = 5
    BOUNDARY_COOLDOWN = 2

    NORM_RMS = 0.08
    NORM_TEMPO_MIN = 50.0
    NORM_TEMPO_RANGE = 150.0
    NORM_BANDWIDTH = 6000.0
    NORM_CENTROID = 5000.0
    NORM_ZCR = 0.15
    NORM_HARMONIC = 1.5
    NORM_CONTRAST = 35.0
    NORM_ONSET = 1.5
    NORM_ROLLOFF = 8000.0

    def __init__(self, capture_manager: AudioCaptureManager):
        self._capture = capture_manager
        self._running = False
        self._thread: threading.Thread | None = None
        self._signals = AnalyzerSignals()
        self._recent_quadrants: deque[str] = deque(maxlen=self.HISTORY_SIZE)
        self._recent_coords: deque[tuple[float, float]] = deque(maxlen=self.COORD_HISTORY)
        self._boundary_countdown: int = 0
        self._boundary_cooldown: int = 0
        self._current_confidence: float = 0.0
        self._warmup_window: float = self.WARMUP_START
        self._locked: bool = False
        self._locked_quadrant: str = ""
        self._locked_arousal: float = 0.0
        self._locked_valence: float = 0.0
        self._feature_buffer: deque[dict] = deque(maxlen=self.FEATURE_BUFFER_SIZE)
        self._smoothed_features: dict = {}

    @property
    def signals(self) -> AnalyzerSignals:
        return self._signals

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._reset_state()
        self._thread = threading.Thread(target=self._analysis_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None

    def _reset_state(self) -> None:
        self._recent_quadrants.clear()
        self._recent_coords.clear()
        self._boundary_countdown = 0
        self._boundary_cooldown = 0
        self._warmup_window = self.WARMUP_START
        self._locked = False
        self._locked_quadrant = ""
        self._feature_buffer.clear()
        self._smoothed_features = {}

    def _analysis_loop(self) -> None:
        silence_streak = 0
        while self._running:
            try:
                audio = self._capture.get_snapshot(self._warmup_window)
                if audio is not None:
                    mono = np.mean(audio, axis=0).astype(np.float32)
                    rms = float(np.sqrt(np.mean(mono ** 2)))
                    if rms < self.SILENCE_RMS_THRESHOLD:
                        silence_streak += 1
                        if silence_streak >= 3:
                            self._signals.no_audio.emit()
                        event = threading.Event()
                        event.wait(timeout=self.ANALYSIS_INTERVAL)
                        continue
                    silence_streak = 0
                    result = self._analyze_chunk(mono, 48000)
                    self._handle_result(result)
                    if self._warmup_window < self.SNAPSHOT_SECONDS:
                        self._warmup_window = min(
                            self._warmup_window + self.WARMUP_STEP,
                            self.SNAPSHOT_SECONDS
                        )
                else:
                    event = threading.Event()
                    event.wait(timeout=self.ANALYSIS_INTERVAL)
                    continue
            except Exception as e:
                self._signals.analysis_error.emit(str(e))

            event = threading.Event()
            event.wait(timeout=self.ANALYSIS_INTERVAL)

    def _handle_result(self, result: MoodCoordinates) -> None:
        coord = (result.arousal, result.valence)

        if self._detect_boundary(coord):
            self._recent_quadrants.clear()
            self._recent_coords.clear()
            self._boundary_countdown = self.STABILIZATION_COUNT
            self._boundary_cooldown = self.BOUNDARY_COOLDOWN
            self._warmup_window = self.WARMUP_START
            self._locked = False
            self._locked_quadrant = ""
            self._feature_buffer.clear()
            self._smoothed_features = {}
            self._signals.boundary_detected.emit()

        self._recent_coords.append(coord)

        if not self._locked:
            self._recent_quadrants.append(result.quadrant)

        if self._locked:
            self._signals.mood_analyzed.emit(
                self._locked_arousal, self._locked_valence,
                self._locked_quadrant, 1.0
            )
            return

        if self._boundary_countdown > 0:
            self._boundary_countdown -= 1
            result.confidence = 0.0
        else:
            result.confidence = self._compute_confidence(result)

        self._current_confidence = result.confidence

        if result.confidence >= self.LOCK_CONFIDENCE:
            self._locked = True
            self._locked_quadrant = result.quadrant
            self._locked_arousal = result.arousal
            self._locked_valence = result.valence

        self._signals.mood_analyzed.emit(
            result.arousal, result.valence,
            result.quadrant, result.confidence
        )

    def _detect_boundary(self, current: tuple[float, float]) -> bool:
        if self._boundary_cooldown > 0:
            self._boundary_cooldown -= 1
            return False
        if len(self._recent_coords) < 3:
            return False

        coords = list(self._recent_coords)
        mean_arousal = sum(c[0] for c in coords) / len(coords)
        mean_valence = sum(c[1] for c in coords) / len(coords)

        da = current[0] - mean_arousal
        dv = current[1] - mean_valence
        distance = (da * da + dv * dv) ** 0.5

        threshold = self.BOUNDARY_THRESHOLD_LOCKED if self._locked else self.BOUNDARY_THRESHOLD
        return distance > threshold

    def _analyze_chunk(self, audio: np.ndarray, sr: int) -> MoodCoordinates:
        features = self._extract_features(audio, sr)
        smoothed = self._apply_temporal_smoothing(features)
        return self._map_to_quadrant(smoothed)

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

        contrast = librosa.feature.spectral_contrast(y=audio, sr=sr, n_bands=6)
        contrast_val = float(np.mean(contrast))

        flatness = librosa.feature.spectral_flatness(y=audio)[0]
        flatness_val = float(np.mean(flatness))

        onset_env = librosa.onset.onset_strength(y=audio, sr=sr)
        onset_val = float(np.mean(np.log1p(onset_env)))

        rolloff = librosa.feature.spectral_rolloff(y=audio, sr=sr)[0]
        rolloff_val = float(np.mean(rolloff))

        mfcc = librosa.feature.mfcc(y=audio, sr=sr, n_mfcc=13)
        mfcc_val = float(np.mean(np.abs(mfcc[1:])))

        return {
            "rms_norm": min(rms_val / self.NORM_RMS, 1.0),
            "tempo_bpm": tempo_val,
            "tempo_norm": min(max((tempo_val - self.NORM_TEMPO_MIN) / self.NORM_TEMPO_RANGE, 0.0), 1.0),
            "bandwidth_norm": min(bandwidth_val / self.NORM_BANDWIDTH, 1.0),
            "centroid_norm": min(centroid_val / self.NORM_CENTROID, 1.0),
            "zcr_norm": min(zcr_val / self.NORM_ZCR, 1.0),
            "harmonic_ratio": min(harmonic_ratio / self.NORM_HARMONIC, 1.0),
            "spectral_contrast": min(contrast_val / self.NORM_CONTRAST, 1.0),
            "flatness": min(flatness_val * 10.0, 1.0),
            "onset_strength": min(onset_val / self.NORM_ONSET, 1.0),
            "rolloff_norm": min(rolloff_val / self.NORM_ROLLOFF, 1.0),
            "mfcc_val": mfcc_val,
        }

    def _apply_temporal_smoothing(self, features: dict) -> dict:
        self._feature_buffer.append(features)

        if not self._smoothed_features:
            self._smoothed_features = {k: v for k, v in features.items()}
            return dict(self._smoothed_features)

        alpha = self.FEATURE_EMA_ALPHA
        for key in features:
            if key in self._smoothed_features:
                self._smoothed_features[key] = (
                    alpha * features[key] + (1 - alpha) * self._smoothed_features[key]
                )
            else:
                self._smoothed_features[key] = features[key]

        return dict(self._smoothed_features)

    def _map_to_quadrant(self, features: dict) -> MoodCoordinates:
        onset = features.get("onset_strength", 0.5)
        contrast = features.get("spectral_contrast", 0.5)
        flatness = features.get("flatness", 0.1)
        rolloff = features.get("rolloff_norm", 0.5)

        arousal_raw = (
            features["tempo_norm"] * 0.35
            + features["rms_norm"] * 0.25
            + features["bandwidth_norm"] * 0.10
            + onset * 0.15
            + rolloff * 0.15
        )

        valence_raw = (
            contrast * 0.30
            + features["centroid_norm"] * 0.15
            + features["harmonic_ratio"] * 0.20
            + rolloff * 0.15
            - features["rms_norm"] * 0.10
            - features["zcr_norm"] * 0.05
            - flatness * 0.05
        )

        arousal = max(-1.0, min(1.0, arousal_raw * 2 - 1))
        valence = max(-1.0, min(1.0, (valence_raw - 0.30) * 2.5))

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

    def _compute_confidence(self, current: MoodCoordinates) -> float:
        if not self._recent_quadrants:
            return 0.0

        quadrants = list(self._recent_quadrants)
        weights = list(range(1, len(quadrants) + 1))
        total_weight = sum(weights)

        weighted_counts: dict[str, float] = {}
        for q, w in zip(quadrants, weights):
            weighted_counts[q] = weighted_counts.get(q, 0.0) + w

        current_quadrant = current.quadrant
        dominant_quadrant = max(weighted_counts, key=weighted_counts.get)

        if current_quadrant != dominant_quadrant:
            return 0.0

        consistency = weighted_counts[dominant_quadrant] / total_weight
        margin = min(abs(current.arousal), abs(current.valence))
        margin_factor = min(margin / 0.4, 1.0)

        return consistency * 0.6 + margin_factor * 0.4
