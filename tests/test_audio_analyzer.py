from unittest.mock import patch, MagicMock

import numpy as np
import pytest

from core.audio_analyzer import AudioAnalyzer, MoodCoordinates


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
        features = {"rms_norm": 0.8, "tempo_norm": 0.7, "bandwidth_norm": 0.6,
                    "centroid_norm": 0.7, "zcr_norm": 0.2, "harmonic_ratio": 0.6}
        result = analyzer._map_to_quadrant(features)
        assert result.quadrant == "VIGOROUS"
        assert result.arousal > 0
        assert result.valence > 0

    def test_tense_quadrant(self):
        analyzer = AudioAnalyzer(MagicMock())
        features = {"rms_norm": 0.8, "tempo_norm": 0.7, "bandwidth_norm": 0.6,
                    "centroid_norm": 0.2, "zcr_norm": 0.8, "harmonic_ratio": 0.2}
        result = analyzer._map_to_quadrant(features)
        assert result.quadrant == "TENSE"
        assert result.arousal > 0
        assert result.valence < 0

    def test_melancholy_quadrant(self):
        analyzer = AudioAnalyzer(MagicMock())
        features = {"rms_norm": 0.2, "tempo_norm": 0.3, "bandwidth_norm": 0.2,
                    "centroid_norm": 0.2, "zcr_norm": 0.7, "harmonic_ratio": 0.3}
        result = analyzer._map_to_quadrant(features)
        assert result.quadrant == "MELANCHOLY"
        assert result.arousal < 0
        assert result.valence < 0

    def test_calm_quadrant(self):
        analyzer = AudioAnalyzer(MagicMock())
        features = {"rms_norm": 0.2, "tempo_norm": 0.2, "bandwidth_norm": 0.2,
                    "centroid_norm": 0.6, "zcr_norm": 0.2, "harmonic_ratio": 0.7}
        result = analyzer._map_to_quadrant(features)
        assert result.quadrant == "CALM"
        assert result.arousal < 0
        assert result.valence > 0

    def test_arousal_bounded(self):
        analyzer = AudioAnalyzer(MagicMock())
        features = {"rms_norm": 1.0, "tempo_norm": 1.0, "bandwidth_norm": 1.0,
                    "centroid_norm": 0.5, "zcr_norm": 0.5, "harmonic_ratio": 0.5}
        result = analyzer._map_to_quadrant(features)
        assert -1.0 <= result.arousal <= 1.0
        assert -1.0 <= result.valence <= 1.0


class TestExtractFeatures:
    @patch("core.audio_analyzer.librosa")
    def test_extract_features_returns_all_keys(self, mock_librosa):
        mock_librosa.feature.rms.return_value = np.array([[0.5]])
        mock_librosa.feature.spectral_centroid.return_value = np.array([[2000.0]])
        mock_librosa.feature.zero_crossing_rate.return_value = np.array([[0.1]])
        mock_librosa.feature.spectral_bandwidth.return_value = np.array([[3000.0]])
        mock_librosa.beat.beat_track.return_value = (np.array([120.0]), np.array([0]))
        mock_librosa.effects.harmonic.return_value = np.zeros(48000)

        analyzer = AudioAnalyzer(MagicMock())
        audio = np.zeros(48000, dtype=np.float32)
        features = analyzer._extract_features(audio, 48000)

        assert "rms_norm" in features
        assert "tempo_norm" in features
        assert "bandwidth_norm" in features
        assert "centroid_norm" in features
        assert "zcr_norm" in features
        assert "harmonic_ratio" in features


class TestConfidence:
    def test_initial_confidence_is_zero(self):
        analyzer = AudioAnalyzer(MagicMock())
        assert analyzer._current_confidence == 0.0

    def test_confidence_increases_with_consistent_results(self):
        analyzer = AudioAnalyzer(MagicMock())
        analyzer._recent_quadrants = ["VIGOROUS", "VIGOROUS", "VIGOROUS"]
        conf = analyzer._compute_confidence()
        assert conf > 0.5

    def test_confidence_low_with_mixed_results(self):
        analyzer = AudioAnalyzer(MagicMock())
        analyzer._recent_quadrants = ["VIGOROUS", "TENSE", "CALM"]
        conf = analyzer._compute_confidence()
        assert conf < 0.5


class TestAnalyzeChunk:
    @patch("core.audio_analyzer.librosa")
    def test_analyze_chunk_returns_mood_coordinates(self, mock_librosa):
        mock_librosa.feature.rms.return_value = np.array([[0.5]])
        mock_librosa.feature.spectral_centroid.return_value = np.array([[2000.0]])
        mock_librosa.feature.zero_crossing_rate.return_value = np.array([[0.1]])
        mock_librosa.feature.spectral_bandwidth.return_value = np.array([[3000.0]])
        mock_librosa.beat.beat_track.return_value = (np.array([120.0]), np.array([0]))
        mock_librosa.effects.harmonic.return_value = np.zeros(48000)

        analyzer = AudioAnalyzer(MagicMock())
        audio = np.random.randn(48000).astype(np.float32) * 0.1
        result = analyzer._analyze_chunk(audio, 48000)

        assert isinstance(result, MoodCoordinates)
        assert result.quadrant in ("VIGOROUS", "TENSE", "MELANCHOLY", "CALM")
        assert -1.0 <= result.arousal <= 1.0
        assert -1.0 <= result.valence <= 1.0
