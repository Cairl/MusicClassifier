from unittest.mock import patch, MagicMock

import numpy as np
import pytest

from core.audio_analyzer import AudioAnalyzer, MoodCoordinates, MoodCoordinates


class TestMoodCoordinates:
    def test_creation(self):
        mc = MoodCoordinates(arousal=0.5, valence=-0.3, quadrant="TENSE", confidence=0.7)
        assert mc.arousal == 0.5
        assert mc.valence == -0.3
        assert mc.quadrant == "TENSE"
        assert mc.confidence == 0.7


class TestMapToQuadrant:
    def test_vigorous_quadrant(self):
        analyzer = AudioAnalyzer(MagicMock())
        features = {"rms_norm": 0.7, "tempo_norm": 0.6, "bandwidth_norm": 0.6,
                    "centroid_norm": 0.5, "zcr_norm": 0.3, "harmonic_ratio": 0.5,
                    "spectral_contrast": 0.6, "flatness": 0.1, "onset_strength": 0.6,
                    "rolloff_norm": 0.6}
        result = analyzer._map_to_quadrant(features)
        assert result.quadrant == "VIGOROUS"
        assert result.arousal > 0
        assert result.valence > 0

    def test_tense_quadrant(self):
        analyzer = AudioAnalyzer(MagicMock())
        features = {"rms_norm": 0.7, "tempo_norm": 0.7, "bandwidth_norm": 0.6,
                    "centroid_norm": 0.2, "zcr_norm": 0.8, "harmonic_ratio": 0.2,
                    "spectral_contrast": 0.2, "flatness": 0.4, "onset_strength": 0.7,
                    "rolloff_norm": 0.3}
        result = analyzer._map_to_quadrant(features)
        assert result.quadrant == "TENSE"
        assert result.arousal > 0
        assert result.valence < 0

    def test_melancholy_quadrant(self):
        analyzer = AudioAnalyzer(MagicMock())
        features = {"rms_norm": 0.3, "tempo_norm": 0.2, "bandwidth_norm": 0.3,
                    "centroid_norm": 0.2, "zcr_norm": 0.4, "harmonic_ratio": 0.33,
                    "spectral_contrast": 0.3, "flatness": 0.2, "onset_strength": 0.2,
                    "rolloff_norm": 0.3}
        result = analyzer._map_to_quadrant(features)
        assert result.quadrant == "MELANCHOLY"
        assert result.arousal < 0
        assert result.valence < 0

    def test_calm_quadrant(self):
        analyzer = AudioAnalyzer(MagicMock())
        features = {"rms_norm": 0.2, "tempo_norm": 0.2, "bandwidth_norm": 0.2,
                    "centroid_norm": 0.6, "zcr_norm": 0.2, "harmonic_ratio": 0.7,
                    "spectral_contrast": 0.6, "flatness": 0.05, "onset_strength": 0.15,
                    "rolloff_norm": 0.6}
        result = analyzer._map_to_quadrant(features)
        assert result.quadrant == "CALM"
        assert result.arousal < 0
        assert result.valence > 0

    def test_arousal_bounded(self):
        analyzer = AudioAnalyzer(MagicMock())
        features = {"rms_norm": 1.0, "tempo_norm": 1.0, "bandwidth_norm": 1.0,
                    "centroid_norm": 0.5, "zcr_norm": 0.5, "harmonic_ratio": 0.5,
                    "spectral_contrast": 1.0, "flatness": 1.0, "onset_strength": 1.0,
                    "rolloff_norm": 1.0}
        result = analyzer._map_to_quadrant(features)
        assert -1.0 <= result.arousal <= 1.0
        assert -1.0 <= result.valence <= 1.0

    def test_default_values_for_missing_features(self):
        analyzer = AudioAnalyzer(MagicMock())
        features = {"rms_norm": 0.5, "tempo_norm": 0.5, "bandwidth_norm": 0.5,
                    "centroid_norm": 0.5, "zcr_norm": 0.5, "harmonic_ratio": 0.5}
        result = analyzer._map_to_quadrant(features)
        assert result.quadrant in ("VIGOROUS", "TENSE", "MELANCHOLY", "CALM")
        assert -1.0 <= result.arousal <= 1.0
        assert -1.0 <= result.valence <= 1.0

    def test_high_contrast_shifts_valence_positive(self):
        analyzer = AudioAnalyzer(MagicMock())
        low_contrast = {"rms_norm": 0.5, "tempo_norm": 0.5, "bandwidth_norm": 0.5,
                        "centroid_norm": 0.5, "zcr_norm": 0.5, "harmonic_ratio": 0.5,
                        "spectral_contrast": 0.1, "flatness": 0.1, "onset_strength": 0.5,
                        "rolloff_norm": 0.5}
        high_contrast = {**low_contrast, "spectral_contrast": 0.9}
        low_result = analyzer._map_to_quadrant(low_contrast)
        high_result = analyzer._map_to_quadrant(high_contrast)
        assert high_result.valence > low_result.valence

    def test_onset_strength_increases_arousal(self):
        analyzer = AudioAnalyzer(MagicMock())
        low_onset = {"rms_norm": 0.5, "tempo_norm": 0.5, "bandwidth_norm": 0.5,
                     "centroid_norm": 0.5, "zcr_norm": 0.5, "harmonic_ratio": 0.5,
                     "spectral_contrast": 0.5, "flatness": 0.1, "onset_strength": 0.1,
                     "rolloff_norm": 0.5}
        high_onset = {**low_onset, "onset_strength": 0.9}
        low_result = analyzer._map_to_quadrant(low_onset)
        high_result = analyzer._map_to_quadrant(high_onset)
        assert high_result.arousal > low_result.arousal

    def test_slow_piano_maps_to_calm(self):
        analyzer = AudioAnalyzer(MagicMock())
        features = {"rms_norm": 0.4, "tempo_norm": 0.10, "bandwidth_norm": 0.60,
                    "centroid_norm": 0.40, "zcr_norm": 0.15, "harmonic_ratio": 0.70,
                    "spectral_contrast": 0.60, "flatness": 0.05, "onset_strength": 0.50,
                    "rolloff_norm": 0.35}
        result = analyzer._map_to_quadrant(features)
        assert result.arousal < 0

    def test_rolloff_increases_both_arousal_and_valence(self):
        analyzer = AudioAnalyzer(MagicMock())
        low_rolloff = {"rms_norm": 0.5, "tempo_norm": 0.5, "bandwidth_norm": 0.5,
                       "centroid_norm": 0.5, "zcr_norm": 0.5, "harmonic_ratio": 0.5,
                       "spectral_contrast": 0.5, "flatness": 0.1, "onset_strength": 0.5,
                       "rolloff_norm": 0.1}
        high_rolloff = {**low_rolloff, "rolloff_norm": 0.9}
        low_result = analyzer._map_to_quadrant(low_rolloff)
        high_result = analyzer._map_to_quadrant(high_rolloff)
        assert high_result.arousal > low_result.arousal
        assert high_result.valence > low_result.valence

    def test_tempo_dominates_arousal_for_slow_music(self):
        analyzer = AudioAnalyzer(MagicMock())
        slow_high_features = {
            "rms_norm": 0.5, "tempo_norm": 0.05, "bandwidth_norm": 0.7,
            "centroid_norm": 0.5, "zcr_norm": 0.3, "harmonic_ratio": 0.6,
            "spectral_contrast": 0.5, "flatness": 0.1, "onset_strength": 0.6,
            "rolloff_norm": 0.5,
        }
        result = analyzer._map_to_quadrant(slow_high_features)
        assert result.arousal < 0


class TestExtractFeatures:
    @patch("core.audio_analyzer.librosa")
    def test_extract_features_returns_all_keys(self, mock_librosa):
        mock_librosa.feature.rms.return_value = np.array([[0.5]])
        mock_librosa.feature.spectral_centroid.return_value = np.array([[2000.0]])
        mock_librosa.feature.zero_crossing_rate.return_value = np.array([[0.1]])
        mock_librosa.feature.spectral_bandwidth.return_value = np.array([[3000.0]])
        mock_librosa.beat.beat_track.return_value = (np.array([120.0]), np.array([0]))
        mock_librosa.effects.harmonic.return_value = np.zeros(48000)
        mock_librosa.feature.spectral_contrast.return_value = np.array([[20.0]])
        mock_librosa.feature.spectral_flatness.return_value = np.array([[0.05]])
        mock_librosa.onset.onset_strength.return_value = np.array([0.8])
        mock_librosa.feature.spectral_rolloff.return_value = np.array([[4000.0]])
        mock_librosa.feature.mfcc.return_value = np.zeros((13, 10))

        analyzer = AudioAnalyzer(MagicMock())
        audio = np.zeros(48000, dtype=np.float32)
        features = analyzer._extract_features(audio, 48000)

        assert "rms_norm" in features
        assert "tempo_norm" in features
        assert "bandwidth_norm" in features
        assert "centroid_norm" in features
        assert "zcr_norm" in features
        assert "harmonic_ratio" in features
        assert "spectral_contrast" in features
        assert "flatness" in features
        assert "onset_strength" in features
        assert "rolloff_norm" in features
        assert "mfcc_val" in features

    @patch("core.audio_analyzer.librosa")
    def test_extract_features_normalization_bounds(self, mock_librosa):
        mock_librosa.feature.rms.return_value = np.array([[0.2]])
        mock_librosa.feature.spectral_centroid.return_value = np.array([[8000.0]])
        mock_librosa.feature.zero_crossing_rate.return_value = np.array([[0.3]])
        mock_librosa.feature.spectral_bandwidth.return_value = np.array([[10000.0]])
        mock_librosa.beat.beat_track.return_value = (np.array([250.0]), np.array([0]))
        mock_librosa.effects.harmonic.return_value = np.ones(48000) * 0.5
        mock_librosa.feature.spectral_contrast.return_value = np.array([[50.0]])
        mock_librosa.feature.spectral_flatness.return_value = np.array([[0.2]])
        mock_librosa.onset.onset_strength.return_value = np.array([5.0])
        mock_librosa.feature.spectral_rolloff.return_value = np.array([[12000.0]])
        mock_librosa.feature.mfcc.return_value = np.zeros((13, 10))

        analyzer = AudioAnalyzer(MagicMock())
        audio = np.ones(48000, dtype=np.float32) * 0.1
        features = analyzer._extract_features(audio, 48000)

        for key in ["rms_norm", "tempo_norm", "bandwidth_norm", "centroid_norm",
                     "zcr_norm", "harmonic_ratio", "spectral_contrast",
                     "flatness", "onset_strength", "rolloff_norm"]:
            assert 0.0 <= features[key] <= 1.0


class TestTemporalSmoothing:
    def test_first_frame_returns_raw_features(self):
        analyzer = AudioAnalyzer(MagicMock())
        features = {"rms_norm": 0.8, "tempo_norm": 0.7}
        smoothed = analyzer._apply_temporal_smoothing(features)
        assert smoothed["rms_norm"] == 0.8
        assert smoothed["tempo_norm"] == 0.7

    def test_smoothing_dampens_changes(self):
        analyzer = AudioAnalyzer(MagicMock())
        first = {"rms_norm": 0.5, "tempo_norm": 0.5}
        second = {"rms_norm": 0.9, "tempo_norm": 0.9}

        analyzer._apply_temporal_smoothing(first)
        smoothed = analyzer._apply_temporal_smoothing(second)

        assert smoothed["rms_norm"] < 0.9
        assert smoothed["rms_norm"] > 0.5
        assert smoothed["tempo_norm"] < 0.9
        assert smoothed["tempo_norm"] > 0.5

    def test_smoothing_converges_over_time(self):
        analyzer = AudioAnalyzer(MagicMock())
        initial = {"rms_norm": 0.3}
        analyzer._apply_temporal_smoothing(initial)

        target = {"rms_norm": 0.8}
        for _ in range(20):
            smoothed = analyzer._apply_temporal_smoothing(target)

        assert abs(smoothed["rms_norm"] - 0.8) < 0.05

    def test_feature_buffer_resets_clear_smoothing(self):
        analyzer = AudioAnalyzer(MagicMock())
        analyzer._apply_temporal_smoothing({"rms_norm": 0.5})
        analyzer._apply_temporal_smoothing({"rms_norm": 0.9})

        analyzer._feature_buffer.clear()
        analyzer._smoothed_features = {}
        smoothed = analyzer._apply_temporal_smoothing({"rms_norm": 0.2})
        assert smoothed["rms_norm"] == 0.2


class TestConfidence:
    def test_initial_confidence_is_zero(self):
        analyzer = AudioAnalyzer(MagicMock())
        assert analyzer._current_confidence == 0.0

    def test_confidence_increases_with_consistent_results(self):
        analyzer = AudioAnalyzer(MagicMock())
        analyzer._recent_quadrants = ["VIGOROUS", "VIGOROUS", "VIGOROUS"]
        current = MoodCoordinates(arousal=0.5, valence=0.5, quadrant="VIGOROUS", confidence=0.0)
        conf = analyzer._compute_confidence(current)
        assert conf > 0.5

    def test_confidence_low_with_mixed_results(self):
        analyzer = AudioAnalyzer(MagicMock())
        analyzer._recent_quadrants = ["VIGOROUS", "TENSE", "CALM"]
        current = MoodCoordinates(arousal=0.5, valence=0.5, quadrant="VIGOROUS", confidence=0.0)
        conf = analyzer._compute_confidence(current)
        assert conf < 0.5

    def test_confidence_zero_when_quadrant_disagrees(self):
        analyzer = AudioAnalyzer(MagicMock())
        analyzer._recent_quadrants = ["TENSE", "TENSE", "TENSE"]
        current = MoodCoordinates(arousal=-0.5, valence=0.5, quadrant="CALM", confidence=0.0)
        conf = analyzer._compute_confidence(current)
        assert conf == 0.0

    def test_confidence_higher_near_quadrant_center(self):
        analyzer = AudioAnalyzer(MagicMock())
        analyzer._recent_quadrants = ["VIGOROUS", "VIGOROUS", "VIGOROUS"]
        near_center = MoodCoordinates(arousal=0.6, valence=0.6, quadrant="VIGOROUS", confidence=0.0)
        near_boundary = MoodCoordinates(arousal=0.05, valence=0.05, quadrant="VIGOROUS", confidence=0.0)
        conf_center = analyzer._compute_confidence(near_center)
        conf_boundary = analyzer._compute_confidence(near_boundary)
        assert conf_center > conf_boundary

    def test_recent_frames_weighted_more(self):
        analyzer = AudioAnalyzer(MagicMock())
        analyzer._recent_quadrants = ["TENSE", "VIGOROUS", "VIGOROUS", "VIGOROUS"]
        current = MoodCoordinates(arousal=0.5, valence=0.5, quadrant="VIGOROUS", confidence=0.0)
        conf = analyzer._compute_confidence(current)
        assert conf > 0.5


class TestAnalyzeChunk:
    @patch("core.audio_analyzer.librosa")
    def test_analyze_chunk_returns_mood_coordinates(self, mock_librosa):
        mock_librosa.feature.rms.return_value = np.array([[0.5]])
        mock_librosa.feature.spectral_centroid.return_value = np.array([[2000.0]])
        mock_librosa.feature.zero_crossing_rate.return_value = np.array([[0.1]])
        mock_librosa.feature.spectral_bandwidth.return_value = np.array([[3000.0]])
        mock_librosa.beat.beat_track.return_value = (np.array([120.0]), np.array([0]))
        mock_librosa.effects.harmonic.return_value = np.zeros(48000)
        mock_librosa.feature.spectral_contrast.return_value = np.array([[20.0]])
        mock_librosa.feature.spectral_flatness.return_value = np.array([[0.05]])
        mock_librosa.onset.onset_strength.return_value = np.array([0.8])
        mock_librosa.feature.spectral_rolloff.return_value = np.array([[4000.0]])
        mock_librosa.feature.mfcc.return_value = np.zeros((13, 10))

        analyzer = AudioAnalyzer(MagicMock())
        audio = np.random.randn(48000).astype(np.float32) * 0.1
        result = analyzer._analyze_chunk(audio, 48000)

        assert isinstance(result, MoodCoordinates)
        assert result.quadrant in ("VIGOROUS", "TENSE", "MELANCHOLY", "CALM")
        assert -1.0 <= result.arousal <= 1.0
        assert -1.0 <= result.valence <= 1.0


class TestBoundaryDetection:
    def test_cooldown_prevents_immediate_re_trigger(self):
        analyzer = AudioAnalyzer(MagicMock())
        analyzer._boundary_cooldown = 2
        analyzer._recent_coords = [(0.5, 0.5), (0.5, 0.5), (0.5, 0.5)]
        result = analyzer._detect_boundary((-0.8, -0.8), MoodCoordinates(-0.8, -0.8, "TENSE", 0.0))
        assert result is False
        assert analyzer._boundary_cooldown == 1

    def test_boundary_detected_with_large_deviation(self):
        analyzer = AudioAnalyzer(MagicMock())
        analyzer._recent_coords = [(0.3, 0.3), (0.35, 0.35), (0.3, 0.3)]
        result = analyzer._detect_boundary((-0.8, -0.8), MoodCoordinates(-0.8, -0.8, "TENSE", 0.0))
        assert result is True

    def test_no_boundary_with_small_deviation(self):
        analyzer = AudioAnalyzer(MagicMock())
        analyzer._recent_coords = [(0.3, 0.3), (0.35, 0.35), (0.3, 0.3)]
        result = analyzer._detect_boundary((0.32, 0.32), MoodCoordinates(0.32, 0.32, "VIGOROUS", 0.0))
        assert result is False

    def test_insufficient_coords_skips_detection(self):
        analyzer = AudioAnalyzer(MagicMock())
        analyzer._recent_coords = [(0.3, 0.3)]
        result = analyzer._detect_boundary((-0.8, -0.8), MoodCoordinates(-0.8, -0.8, "TENSE", 0.0))
        assert result is False


class TestMusic2EmoPath:
    def _analyzer_with_client(self, predict_return=None, side_effect=None):
        client = MagicMock()
        client.available = True
        if side_effect is not None:
            client.predict_audio.side_effect = side_effect
        else:
            client.predict_audio.return_value = predict_return
        analyzer = AudioAnalyzer(MagicMock(), music2emo_client=client)
        analyzer._signals = MagicMock()
        return analyzer, client

    def _audio(self):
        return np.zeros(48000, dtype=np.float32)

    def test_vigorous_mapping(self):
        analyzer, _ = self._analyzer_with_client({"valence": 9.0, "arousal": 9.0, "moods": []})
        result = analyzer._analyze_chunk(self._audio(), 48000)
        assert result.quadrant == "VIGOROUS"
        assert result.arousal > 0.9
        assert result.valence > 0.9

    def test_melancholy_mapping(self):
        analyzer, _ = self._analyzer_with_client({"valence": 1.0, "arousal": 1.0, "moods": []})
        result = analyzer._analyze_chunk(self._audio(), 48000)
        assert result.quadrant == "MELANCHOLY"
        assert result.arousal < -0.9
        assert result.valence < -0.9

    def test_tense_mapping(self):
        analyzer, _ = self._analyzer_with_client({"valence": 1.0, "arousal": 9.0, "moods": []})
        result = analyzer._analyze_chunk(self._audio(), 48000)
        assert result.quadrant == "TENSE"

    def test_calm_mapping(self):
        analyzer, _ = self._analyzer_with_client({"valence": 9.0, "arousal": 1.0, "moods": []})
        result = analyzer._analyze_chunk(self._audio(), 48000)
        assert result.quadrant == "CALM"

    def test_midpoint_is_near_zero(self):
        analyzer, _ = self._analyzer_with_client({"valence": 5.0, "arousal": 5.0, "moods": []})
        result = analyzer._analyze_chunk(self._audio(), 48000)
        assert abs(result.arousal) < 0.05
        assert abs(result.valence) < 0.05

    def test_smooth_va_dampens_change(self):
        analyzer, _ = self._analyzer_with_client({"valence": 9.0, "arousal": 9.0, "moods": []})
        analyzer._analyze_chunk(self._audio(), 48000)
        analyzer._m2e_client.predict_audio.return_value = {"valence": 1.0, "arousal": 1.0, "moods": []}
        result = analyzer._analyze_chunk(self._audio(), 48000)
        assert -1.0 < result.arousal < 1.0
        assert result.arousal > -1.0
        assert result.valence > -1.0

    @patch("core.audio_analyzer.librosa")
    def test_predict_error_falls_back_to_librosa(self, mock_librosa):
        self._stub_librosa(mock_librosa)
        analyzer, _ = self._analyzer_with_client({"error": "boom"})
        result = analyzer._analyze_chunk(np.ones(48000, dtype=np.float32) * 0.1, 48000)
        assert result.quadrant in ("VIGOROUS", "TENSE", "MELANCHOLY", "CALM")
        assert -1.0 <= result.arousal <= 1.0

    @patch("core.audio_analyzer.librosa")
    def test_predict_exception_falls_back_to_librosa(self, mock_librosa):
        self._stub_librosa(mock_librosa)
        analyzer, _ = self._analyzer_with_client(side_effect=RuntimeError("server dead"))
        result = analyzer._analyze_chunk(np.ones(48000, dtype=np.float32) * 0.1, 48000)
        assert result.quadrant in ("VIGOROUS", "TENSE", "MELANCHOLY", "CALM")

    def test_no_client_skips_music2emo(self):
        analyzer = AudioAnalyzer(MagicMock())
        assert analyzer._m2e_client is None

    def test_reset_clears_va_smoothing(self):
        analyzer, _ = self._analyzer_with_client({"valence": 9.0, "arousal": 9.0, "moods": []})
        analyzer._analyze_chunk(self._audio(), 48000)
        assert analyzer._last_va is not None
        analyzer._reset_state()
        assert analyzer._last_va is None

    @staticmethod
    def _stub_librosa(mock_librosa):
        mock_librosa.feature.rms.return_value = np.array([[0.5]])
        mock_librosa.feature.spectral_centroid.return_value = np.array([[2000.0]])
        mock_librosa.feature.zero_crossing_rate.return_value = np.array([[0.1]])
        mock_librosa.feature.spectral_bandwidth.return_value = np.array([[3000.0]])
        mock_librosa.beat.beat_track.return_value = (np.array([120.0]), np.array([0]))
        mock_librosa.effects.harmonic.return_value = np.zeros(48000)
        mock_librosa.feature.spectral_contrast.return_value = np.array([[20.0]])
        mock_librosa.feature.spectral_flatness.return_value = np.array([[0.05]])
        mock_librosa.onset.onset_strength.return_value = np.array([0.8])
        mock_librosa.feature.spectral_rolloff.return_value = np.array([[4000.0]])
        mock_librosa.feature.mfcc.return_value = np.zeros((13, 10))
