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
    SILENCE_RMS_THRESHOLD = 0.008  # below this = no music playing

    def __init__(self, capture_manager: AudioCaptureManager):
        self._capture = capture_manager
        self._running = False
        self._thread: threading.Thread | None = None
        self._signals = AnalyzerSignals()
        self._recent_quadrants: deque[str] = deque(maxlen=self.HISTORY_SIZE)
        self._recent_coords: deque[tuple[float, float]] = deque(maxlen=self.COORD_HISTORY)
        self._boundary_countdown: int = 0
        self._current_confidence: float = 0.0
        self._warmup_window: float = self.WARMUP_START
        self._locked: bool = False
        self._locked_quadrant: str = ""
        self._locked_arousal: float = 0.0
        self._locked_valence: float = 0.0

    @property
    def signals(self) -> AnalyzerSignals:
        return self._signals

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._recent_quadrants.clear()
        self._recent_coords.clear()
        self._boundary_countdown = 0
        self._warmup_window = self.WARMUP_START
        self._locked = False
        self._locked_quadrant = ""
        self._thread = threading.Thread(target=self._analysis_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None

    def _analysis_loop(self) -> None:
        silence_streak = 0
        while self._running:
            try:
                audio = self._capture.get_snapshot(self._warmup_window)
                if audio is not None:
                    mono = np.mean(audio, axis=0).astype(np.float32)
                    # Skip analysis if audio is too quiet (no music playing)
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
            self._warmup_window = self.WARMUP_START
            self._locked = False
            self._locked_quadrant = ""
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
            result.confidence = self._compute_confidence()

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

        # MFCC rough proxy: higher = more melodic structure
        mfcc = librosa.feature.mfcc(y=audio, sr=sr, n_mfcc=3)
        mfcc_val = float(np.mean(mfcc[1:]))  # skip 0th coefficient (energy)

        return {
            "rms_norm": min(rms_val / 0.08, 1.0),
            "tempo_bpm": tempo_val,
            "tempo_norm": min(max((tempo_val - 50) / 150, 0.0), 1.0),
            "bandwidth_norm": min(bandwidth_val / 6000.0, 1.0),
            "centroid_norm": min(centroid_val / 5000.0, 1.0),
            "zcr_norm": min(zcr_val / 0.15, 1.0),
            "harmonic_ratio": min(harmonic_ratio / 1.5, 1.0),
        }

    def _map_to_quadrant(self, features: dict) -> MoodCoordinates:
        # Arousal: energy level
        #   BPM/tempo (40%) — fastest indicator of energy
        #   RMS loudness (35%) — volume
        #   Spectral bandwidth (25%) — spectral spread
        arousal_raw = (
            features["tempo_norm"] * 0.40
            + features["rms_norm"] * 0.35
            + features["bandwidth_norm"] * 0.25
        )

        # Valence: positivity
        #   Harmonic ratio (45%) — tonal/harmonic = pleasant
        #   Centroid (30%) — bright = positive
        #   RMS (-15%) — very loud = aggressive
        #   ZCR (-10%) — noisy = negative
        valence_raw = (
            features["harmonic_ratio"] * 0.45
            + features["centroid_norm"] * 0.30
            - features["rms_norm"] * 0.15
            - features["zcr_norm"] * 0.10
        )

        arousal = max(-1.0, min(1.0, arousal_raw * 2 - 1))
        # valence_raw ≈ 0.3–0.8 for most music → map 0.35→0, 0.8→1
        valence = max(-1.0, min(1.0, (valence_raw - 0.35) * 3.0))

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