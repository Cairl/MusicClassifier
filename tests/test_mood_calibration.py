import numpy as np

from core.mood_calibration import Calibrator, CalibrationSample, CalibrationStore


def make_samples(n, raw_offset=0.0):
    return [
        CalibrationSample(
            raw_valence=1.0 + 8.0 * i / max(n - 1, 1),
            raw_arousal=1.0 + 8.0 * i / max(n - 1, 1),
            user_valence=-0.8 + 1.6 * i / max(n - 1, 1) + raw_offset,
            user_arousal=-0.8 + 1.6 * i / max(n - 1, 1),
            timestamp=1000.0 + i,
        )
        for i in range(n)
    ]


def test_store_persists_and_loads(tmp_path):
    path = str(tmp_path / "cal.json")
    store = CalibrationStore(path)
    store.add(make_samples(1)[0])
    reloaded = CalibrationStore(path)
    assert len(reloaded.samples) == 1
    assert reloaded.samples[0].raw_valence == 1.0


def test_store_handles_missing_file(tmp_path):
    store = CalibrationStore(str(tmp_path / "nope.json"))
    assert store.samples == []


def test_calibrator_identity_below_min_samples(tmp_path):
    store = CalibrationStore(str(tmp_path / "cal.json"))
    for s in make_samples(5):
        store.add(s)
    cal = Calibrator(store)
    assert cal.active is False
    v, a = cal.calibrate(7.0, 3.0)
    assert v == (7.0 - 5.0) / 4.0
    assert a == (3.0 - 5.0) / 4.0


def test_calibrator_fits_isotonic_at_min_samples(tmp_path):
    store = CalibrationStore(str(tmp_path / "cal.json"))
    for s in make_samples(12):
        store.add(s)
    cal = Calibrator(store)
    assert cal.active is True
    v, a = cal.calibrate(9.0, 9.0)
    assert v > 0.6
    assert a > 0.6
    v_low, _ = cal.calibrate(1.0, 1.0)
    assert v_low < -0.6


def test_calibrator_clips_out_of_bounds(tmp_path):
    store = CalibrationStore(str(tmp_path / "cal.json"))
    for s in make_samples(12):
        store.add(s)
    cal = Calibrator(store)
    v, a = cal.calibrate(99.0, -5.0)
    assert -1.0 <= v <= 1.0
    assert -1.0 <= a <= 1.0


def test_refit_after_adding_samples(tmp_path):
    store = CalibrationStore(str(tmp_path / "cal.json"))
    cal = Calibrator(store)
    assert cal.active is False
    for s in make_samples(12):
        store.add(s)
    cal.refit()
    assert cal.active is True
