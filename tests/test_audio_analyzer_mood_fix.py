from unittest.mock import MagicMock

import numpy as np
import pytest

from core.audio_analyzer import AudioAnalyzer

GOOD_RESPONSE = {"valence": 7.0, "arousal": 6.0, "moods": ["happy"], "device": "cuda"}


def make_analyzer(predict_return=GOOD_RESPONSE, side_effect=None, available=True):
    client = MagicMock()
    client.available = available
    client.predict_audio.return_value = predict_return
    if side_effect is not None:
        client.predict_audio.side_effect = side_effect
    capture = MagicMock()
    capture.sample_rate = 48000
    analyzer = AudioAnalyzer(capture, music2emo_client=client)
    analyzer._signals = MagicMock()
    return analyzer, capture, client


def good_audio(seconds=10.0, sr=48000):
    n = int(seconds * sr)
    rng = np.random.default_rng(42)
    return (rng.standard_normal((2, n)) * 0.1).astype(np.float32)


def test_analyze_chunk_uses_music2emo_without_fallback():
    analyzer, _, client = make_analyzer()
    result = analyzer._analyze_chunk(good_audio()[0], 48000)
    assert result is not None
    assert client.predict_audio.called
    assert -1.0 <= result.arousal <= 1.0
    assert -1.0 <= result.valence <= 1.0


def test_engine_unavailable_emits_error_no_librosa():
    analyzer, _, _ = make_analyzer(available=False)
    result = analyzer._analyze_chunk(good_audio()[0], 48000)
    assert result is None
    assert analyzer._signals.analysis_error.emit.called


def test_engine_exception_raises_for_loop_restart():
    analyzer, _, _ = make_analyzer(side_effect=RuntimeError("server dead"))
    with pytest.raises(RuntimeError):
        analyzer._analyze_chunk(good_audio()[0], 48000)


def test_engine_error_response_returns_none_and_emits():
    analyzer, _, _ = make_analyzer(predict_return={"error": "boom"})
    result = analyzer._analyze_chunk(good_audio()[0], 48000)
    assert result is None
    assert analyzer._signals.analysis_error.emit.called


def test_loop_restarts_engine_once_then_stops():
    analyzer, capture, client = make_analyzer(side_effect=RuntimeError("boom"))
    capture.get_snapshot.return_value = good_audio()
    analyzer._running = True

    analyzer._analysis_loop()

    assert client.restart.call_count == 1
    assert analyzer._running is False


def test_loop_skips_when_insufficient_audio():
    analyzer, capture, _ = make_analyzer()
    calls = []

    def short_audio_then_stop(seconds):
        calls.append(seconds)
        analyzer._running = False
        return good_audio(seconds=2.0)

    capture.get_snapshot.side_effect = short_audio_then_stop
    analyzer._running = True

    analyzer._analysis_loop()

    assert analyzer._signals.mood_analyzed.emit.call_count == 0


def test_sliding_window_requests_window_seconds():
    analyzer, capture, _ = make_analyzer()
    capture.get_snapshot.return_value = good_audio()
    requested = []
    capture.get_snapshot.side_effect = lambda s: (requested.append(s), good_audio())[1]
    analyzer._running = True

    calls = []

    def stop_after_first(*args):
        calls.append(args)
        analyzer._running = False

    analyzer._signals.mood_analyzed.emit = stop_after_first
    analyzer._analysis_loop()

    assert requested and requested[0] == AudioAnalyzer.WINDOW_SECONDS
    assert len(calls) == 1


def test_quadrant_hysteresis_ignores_small_axis_crossing():
    analyzer = AudioAnalyzer(MagicMock())

    assert analyzer._quadrant_from_va(0.5, 0.2) == "VIGOROUS"
    assert analyzer._quadrant_from_va(0.5, -0.03) == "VIGOROUS"


def test_quadrant_hysteresis_allows_clear_transition():
    analyzer = AudioAnalyzer(MagicMock())

    assert analyzer._quadrant_from_va(0.5, 0.2) == "VIGOROUS"
    assert analyzer._quadrant_from_va(0.5, -0.3) == "TENSE"


def test_quadrant_hysteresis_allows_diagonal_transition():
    analyzer = AudioAnalyzer(MagicMock())

    assert analyzer._quadrant_from_va(0.5, 0.2) == "VIGOROUS"
    assert analyzer._quadrant_from_va(-0.03, -0.9) == "MELANCHOLY"


def test_reset_clears_quadrant_hysteresis():
    analyzer = AudioAnalyzer(MagicMock())
    analyzer._quadrant_from_va(0.5, 0.2)

    analyzer._reset_state()

    assert analyzer._quadrant_from_va(0.5, -0.03) == "TENSE"


def test_calibrator_applied_when_set():
    analyzer, _, _ = make_analyzer()
    calibrator = MagicMock()
    calibrator.calibrate.return_value = (0.9, -0.9)
    analyzer.set_calibrator(calibrator)

    result = analyzer._analyze_chunk(good_audio()[0], 48000)

    assert result is not None
    assert abs(result.valence - 0.9) < 0.35
    assert abs(result.arousal - (-0.9)) < 0.35
    assert calibrator.calibrate.call_count == 1
    args = calibrator.calibrate.call_args[0]
    assert abs(args[0] - 7.0) < 1e-6
    assert abs(args[1] - 6.0) < 1e-6


def test_last_raw_va_updated():
    analyzer, _, _ = make_analyzer()
    analyzer._analyze_chunk(good_audio()[0], 48000)
    assert analyzer.last_raw_va == (7.0, 6.0)
