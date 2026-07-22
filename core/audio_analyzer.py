import threading
import time
from collections import deque
from dataclasses import dataclass

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
    WINDOW_SECONDS = 10.0
    HOP_SECONDS = 2.0
    MIN_AUDIO_SECONDS = 4.0
    HISTORY_SIZE = 7
    BOUNDARY_THRESHOLD = 0.8
    BOUNDARY_THRESHOLD_LOCKED = 1.0
    STABILIZATION_COUNT = 4
    COORD_HISTORY = 5
    LOCK_CONFIDENCE = 0.6
    SILENCE_RMS_THRESHOLD = 0.003

    FEATURE_EMA_ALPHA = 0.5
    BOUNDARY_COOLDOWN = 2
    QUADRANT_DEADZONE = 0.08

    def __init__(self, capture_manager: AudioCaptureManager,
                 music2emo_client=None):
        self._capture = capture_manager
        self._m2e_client = music2emo_client
        self._calibrator = None
        self._running = False
        self._thread: threading.Thread | None = None
        self._signals = AnalyzerSignals()
        self._recent_quadrants: deque[str] = deque(maxlen=self.HISTORY_SIZE)
        self._recent_coords: deque[tuple[float, float]] = deque(maxlen=self.COORD_HISTORY)
        self._boundary_countdown: int = 0
        self._boundary_cooldown: int = 0
        self._current_confidence: float = 0.0
        self._locked: bool = False
        self._locked_quadrant: str = ""
        self._locked_arousal: float = 0.0
        self._locked_valence: float = 0.0
        self._last_va: tuple[float, float] | None = None
        self._last_raw_va: tuple[float, float] | None = None
        self._last_quadrant = ""
        self._restart_attempted = False

    @property
    def signals(self) -> AnalyzerSignals:
        return self._signals

    @property
    def last_raw_va(self) -> tuple[float, float] | None:
        return self._last_raw_va

    def set_calibrator(self, calibrator) -> None:
        self._calibrator = calibrator

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
        if self._m2e_client is not None:
            self._m2e_client.stop()

    def force_reset(self) -> None:
        self._reset_state()

    def _reset_state(self) -> None:
        self._recent_quadrants.clear()
        self._recent_coords.clear()
        self._boundary_countdown = 0
        self._boundary_cooldown = 0
        self._locked = False
        self._locked_quadrant = ""
        self._last_va = None
        self._last_raw_va = None
        self._last_quadrant = ""
        self._restart_attempted = False

    def _analysis_loop(self) -> None:
        silence_streak = 0
        while self._running:
            cycle_start = time.monotonic()
            try:
                audio = self._capture.get_snapshot(self.WINDOW_SECONDS)
                if audio is None or audio.shape[1] < int(self.MIN_AUDIO_SECONDS * self._capture.sample_rate):
                    self._wait_next_cycle(cycle_start)
                    continue
                mono = np.mean(audio, axis=0).astype(np.float32)
                rms = float(np.sqrt(np.mean(mono ** 2)))
                if rms < self.SILENCE_RMS_THRESHOLD:
                    silence_streak += 1
                    if silence_streak >= 3:
                        self._signals.no_audio.emit()
                    self._wait_next_cycle(cycle_start)
                    continue
                silence_streak = 0
                result = self._analyze_chunk(mono, self._capture.sample_rate)
                if result is not None:
                    self._handle_result(result)
            except Exception as e:
                if not self._try_restart_engine(str(e)):
                    self._running = False
                    return
            self._wait_next_cycle(cycle_start)

    def _wait_next_cycle(self, cycle_start: float) -> None:
        elapsed = time.monotonic() - cycle_start
        remaining = self.HOP_SECONDS - elapsed
        if remaining > 0:
            threading.Event().wait(timeout=remaining)

    def _try_restart_engine(self, error: str) -> bool:
        if self._restart_attempted or self._m2e_client is None:
            self._signals.analysis_error.emit(f"情绪引擎已停止: {error}")
            return False
        self._restart_attempted = True
        try:
            self._m2e_client.restart()
            return True
        except Exception as exc:
            self._signals.analysis_error.emit(f"情绪引擎已停止: {exc}")
            return False

    def _handle_result(self, result: MoodCoordinates) -> None:
        coord = (result.arousal, result.valence)

        if self._detect_boundary(coord, result):
            self._recent_quadrants.clear()
            self._recent_coords.clear()
            self._boundary_countdown = self.STABILIZATION_COUNT
            self._boundary_cooldown = self.BOUNDARY_COOLDOWN
            self._locked = False
            self._locked_quadrant = ""
            self._signals.boundary_detected.emit()

        self._recent_coords.append(coord)
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

    def _detect_boundary(self, current: tuple[float, float],
                         result: MoodCoordinates) -> bool:
        if self._boundary_cooldown > 0:
            self._boundary_cooldown -= 1
            return False

        if self._locked and result.quadrant != self._locked_quadrant:
            return True

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

    def _analyze_chunk(self, audio: np.ndarray, sr: int) -> MoodCoordinates | None:
        if self._m2e_client is None or not self._m2e_client.available:
            self._signals.analysis_error.emit("情绪引擎不可用，请检查 music2emo 安装")
            return None
        try:
            out = self._m2e_client.predict_audio(audio, sr)
        except Exception as exc:
            raise RuntimeError(f"music2emo predict failed: {exc}") from exc
        if not isinstance(out, dict) or "error" in out:
            self._signals.analysis_error.emit(
                f"music2emo error: {out.get('error') if isinstance(out, dict) else out}")
            return None
        try:
            raw_arousal = float(out["arousal"])
            raw_valence = float(out["valence"])
            if not np.isfinite(raw_arousal) or not np.isfinite(raw_valence):
                raise ValueError("valence/arousal is not finite")
        except (KeyError, TypeError, ValueError) as exc:
            self._signals.analysis_error.emit(f"music2emo returned invalid scores: {exc}")
            return None

        self._last_raw_va = (raw_valence, raw_arousal)

        if self._calibrator is not None:
            valence, arousal = self._calibrator.calibrate(raw_valence, raw_arousal)
        else:
            arousal = self._normalize_model_score(raw_arousal)
            valence = self._normalize_model_score(raw_valence)

        arousal, valence = self._smooth_va(arousal, valence)
        arousal = max(-1.0, min(1.0, arousal))
        valence = max(-1.0, min(1.0, valence))
        quadrant = self._quadrant_from_va(arousal, valence)
        return MoodCoordinates(arousal, valence, quadrant, 0.0)

    @staticmethod
    def _normalize_model_score(score: float) -> float:
        score = max(1.0, min(9.0, score))
        return (score - 5.0) / 4.0

    def _smooth_va(self, arousal: float, valence: float) -> tuple[float, float]:
        if self._last_va is None:
            self._last_va = (arousal, valence)
            return arousal, valence
        alpha = self.FEATURE_EMA_ALPHA
        a = alpha * arousal + (1 - alpha) * self._last_va[0]
        v = alpha * valence + (1 - alpha) * self._last_va[1]
        self._last_va = (a, v)
        return a, v

    def _quadrant_from_va(self, arousal: float, valence: float) -> str:
        if arousal >= 0 and valence >= 0:
            quadrant = "VIGOROUS"
        elif arousal >= 0 and valence < 0:
            quadrant = "TENSE"
        elif arousal < 0 and valence < 0:
            quadrant = "MELANCHOLY"
        else:
            quadrant = "CALM"

        if self._last_quadrant and quadrant != self._last_quadrant:
            last_arousal_positive = self._last_quadrant in {"VIGOROUS", "TENSE"}
            last_valence_positive = self._last_quadrant in {"VIGOROUS", "CALM"}
            arousal_changed = (arousal >= 0) != last_arousal_positive
            valence_changed = (valence >= 0) != last_valence_positive

            if arousal_changed and not valence_changed:
                if abs(arousal) < self.QUADRANT_DEADZONE:
                    return self._last_quadrant
            elif valence_changed and not arousal_changed:
                if abs(valence) < self.QUADRANT_DEADZONE:
                    return self._last_quadrant

        self._last_quadrant = quadrant
        return quadrant

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
