# Mood Analysis Improvement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve song mood classification reliability without changing the existing four-playlist quadrant model.

**Architecture:** Keep music2emo as the preferred analyzer and use librosa as a deterministic fallback whenever the isolated model is unavailable or returns invalid data. Add a small hysteresis zone around the valence/arousal axes so noisy coordinates do not immediately switch quadrants.

**Tech Stack:** Python 3.12, PySide6, NumPy, librosa, pytest, unittest.mock.

## Global Constraints

- Preserve the existing `VIGOROUS`, `TENSE`, `MELANCHOLY`, and `CALM` tags.
- Do not upgrade PaddlePaddle or PaddleOCR dependencies.
- Do not modify OCR, playlist automation, or UI layout in this change.
- Preserve user-deleted legacy test files; add independent regression coverage.
- Production changes must be preceded by failing tests.

---

### Task 1: Add regression tests

**Files:**
- Create: `tests/test_audio_analyzer_mood_fix.py`
- Modify: none

- [x] Add tests for music2emo exception, error payload, unavailable client, invalid scores, and boundary hysteresis.
- [x] Run the new test file and confirm the fallback and hysteresis tests fail against the current implementation.

### Task 2: Restore safe analyzer fallback

**Files:**
- Modify: `core/audio_analyzer.py`
- Test: `tests/test_audio_analyzer_mood_fix.py`

- [x] Return librosa analysis when music2emo is missing, unavailable, raises, returns an error payload, or returns non-finite scores.
- [x] Keep emitting an actionable `analysis_error` signal while returning a real fallback result instead of fixed `CALM` coordinates.
- [x] Clamp valid model scores to the documented 1–9 range before converting to `[-1, 1]`.
- [x] Run the focused tests and confirm they pass.

### Task 3: Add quadrant hysteresis

**Files:**
- Modify: `core/audio_analyzer.py`
- Test: `tests/test_audio_analyzer_mood_fix.py`

- [x] Add a small axis dead zone and remember the previous quadrant.
- [x] Keep the previous quadrant while a coordinate remains inside the dead zone.
- [x] Allow a real transition once the coordinate moves clearly across an axis.
- [x] Clear hysteresis state during analyzer reset.
- [x] Run the focused tests and then the complete available test suite.

### Task 4: Verify and hand off

**Files:**
- Modify: none

- [x] Run `python -m pytest tests/ -v`.
- [x] Review the diff and confirm no deleted user files were restored or modified.
- [x] Report remaining limitations: short audio windows and model calibration still require real-song validation.
