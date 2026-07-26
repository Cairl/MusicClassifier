# AGENTS.md

## Project Overview

MusicClassifier is a Windows-based semi-automated Apple Music song classification tool. It captures the Apple Music window, recognizes song names via OCR (PaddleOCR), lets the user click a target playlist button, and automatically performs mouse clicks to add the song to the playlist.

**Architecture**: Screenshot → OCR recognition → User selection → Simulated mouse clicks. Four core modules are connected through the `TrackInfo` dataclass. All UI automation runs on background threads to keep the PySide6 GUI responsive.

Additionally, the app features a **real-time audio mood analysis** system: it captures process audio from Apple Music via named pipes, predicts valence/arousal via the music2emo engine (MERT-based, isolated subprocess with GPU in-memory inference), optionally applies a personal isotonic-regression calibration layer, then maps the result to a valence-arousal quadrant and recommends the best matching playlist. The librosa fallback path has been removed — when the engine is unavailable or errors, the analyzer emits `analysis_error` and skips that window (no fake coordinates).

**Tech Stack**: Python 3.12, PySide6, PaddleOCR 2.x, PaddlePaddle 2.x, PyAutoGUI, pygetwindow, OpenCV, process-audio-capture, scikit-learn (isotonic regression for calibration); music2emo engine v2 (torch 2.7.1+cu128 + MERT-v1-95M, isolated venv, GPU in-memory inference)

## Setup Commands

- Install dependencies: `pip install -r requirements.txt`
- **Critical**: PaddlePaddle 3.x and PaddleOCR 3.x are incompatible with this project. Version constraints in `requirements.txt` are `paddleocr>=2.7,<3.0` and `paddlepaddle>=2.5,<3.0`. Do not upgrade beyond these ranges.
- Python path on this machine: `C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe`
- **music2emo mood engine v2** (required for mood analysis — there is no longer a librosa fallback): run `music2emo_engine\install.bat` to create an isolated venv (Python 3.12) with torch 2.7.1+cu128 (RTX 5070 / sm_120 needs cu128+) + MERT-v1-95M. First launch downloads the MERT model (~400MB, set `HF_ENDPOINT=https://hf-mirror.com` if HuggingFace is blocked). The engine runs as an isolated subprocess (`music2emo_engine/server.py`) so torch/MERT never pollute the PaddlePaddle host env. Protocol v2: stdin binary frames (8-byte `struct "<II"` header = sample_rate + frame_count, then float32 mono PCM; `frame_count==0xFFFFFFFF` = EXIT), JSON-line responses on stdout, prints `READY v2` after a silent warmup inference. Toggle via `config.json` → `music2emo.enabled`; when off or the venv is absent, `AudioAnalyzer` emits `analysis_error` per window and produces no mood coordinates (it does NOT fall back to librosa).

## Development Workflow

- Run the application: `python main.py`
- **Mood detection starts automatically on launch** (no toggle switch needed)
- The app requires Apple Music to be open on Windows. It finds the window by title "Apple Music" (configurable in `config.json`).
- Before taking a screenshot, the app automatically activates and brings the Apple Music window to the foreground.
- Quadrant chart is always visible, showing "等待音频..." when idle

## Testing Instructions

- Run all tests: `python -m pytest tests/ -v`
- Tests are located in `tests/`, named `test_<module_name>.py`
- 6 test files: `test_audio_analyzer_mood_fix.py` (sliding-window analyzer: engine fallback, restart-once, hysteresis deadzone, calibrator wiring), `test_audio_capture.py` (NamedPipe WAV capture), `test_quadrant_chart.py` (quadrant widget), `test_music2emo_client.py` (binary protocol v2 client: warmup, restart, frame encoding), `test_mood_calibration.py` (CalibrationStore persistence + Calibrator isotonic fit / clipping / out-of-bounds), `test_calibration_popover.py` (3x3 grid dialog signal).
- Tests use `unittest.mock` to mock `pyautogui`, `pygetwindow`, `PaddleOCR`, and the music2emo client. No real windows, OCR, or GPU needed.

## Code Style

- Python 3.12 type annotations: use `X | None` instead of `Optional[X]`, `tuple[int, int]` instead of `Tuple[int, int]`
- Dataclasses for data models (`TrackInfo`, `ClassificationResult`)
- No comments in code unless explicitly requested
- `import pyautogui` and `import pygetwindow` without aliases like `pag`/`pgw` — aliases break `unittest.mock.patch` paths
- GUI updates from background threads must use `PySide6.QtCore.Signal`. Never manipulate UI directly from worker threads.

## UI Design Guidelines

### Visual Style
- Windows native window frame (no `Qt.FramelessWindowHint`)
- Material Design 3 淡灰色系风格
- Background `#fafafa`, sidebar `#ffffff`, card `#ffffff`, secondary `#5f6368`, on-surface `#202124`
- No `Qt.WA_TranslucentBackground` (causes multi-monitor rendering issues)
- No custom `paintEvent` for DPI scaling compatibility

### Layout
|- Sidebar (68px): white background + 1px `#e8eaed` separator; play button at top, library button below
|- Main area: track info card → mood status bar → spectrum bar (16-band FFT) → [playlist grid (left) | quadrant chart (right)] side-by-side
- Window fixed at 620x400 **logical** pixels; Qt6 handles High DPI scaling automatically — never multiply sizes by `devicePixelRatio` manually (causes double-scaling and blurry buttons). All QSS `px` values are logical pixels.
- SVG icons rendered via `QPixmap` must call `setDevicePixelRatio(dpr)` (or be created at `size*dpr`) or they blur on high-DPI screens. See `gui/sidebar.py:_svg_icon`.
- Grid spacing 4px, card padding 10px

### Button States
- Sidebar buttons: transparent background → hover `#e8eaed` circle → pressed `#dadce0`
- Playlist buttons: `#e8eaed` fill + 8px rounded → hover `#dadce0` → pressed `#c4c7c9` → disabled `#f1f3f4` + `#9aa0a6` text
- All fixed pixel values must be scaled by `devicePixelRatio`

## Project Structure

```
MusicClassifier/
├── main.py                  # Entry point
├── config.json              # Playlist hierarchy and action delay config
├── requirements.txt         # Dependencies and version constraints
├── core/
│   ├── models.py            # TrackInfo, ClassificationResult dataclasses
│   ├── screen_capture.py    # Window finding, activation, screenshots
│   ├── ocr_reader.py        # PaddleOCR-based song and playlist name recognition
│   ├── action_executor.py   # Mouse automation (click three-dots menu → add to playlist)
│   ├── playlist_config.py   # Config loading, volume/mood/playlist parsing
│   ├── template_library.py  # Template collection, matching, and missing detection
│   ├── audio_capture.py     # NamedPipe-based Apple Music process audio capture
│   ├── audio_analyzer.py    # 10s/2s sliding-window mood analysis via music2emo engine (no librosa fallback)
│   ├── music2emo_client.py  # Subprocess client: binary PCM protocol v2, warmup, restart-once
│   └── mood_calibration.py  # CalibrationStore (JSON) + Calibrator (isotonic regression, thread-locked)
├── gui/
│   ├── main_window.py       # Main window controller — assembles components, wires signals
│   ├── theme.py             # Design system — color tokens, typography, spacing, shared QSS
│   ├── icons.py             # SVG path icon utilities (play, library, about)
│   ├── sidebar.py           # Sidebar component — play / library / about buttons
│   ├── track_card.py        # Track info card — song name, album
│   ├── playlist_grid.py     # Playlist button grid — 5-column grid from config
│   ├── quadrant_chart.py    # Valence-arousal quadrant visualization
│   ├── calibration_popover.py # 3x3 correction grid dialog for personal calibration
│   ├── highlight_overlay.py # Persistent OCR highlight overlay (in-place rect updates)
│   ├── spectrum_bar.py      # 16-band FFT spectrum bar
│   ├── screenshot_library.py# Screenshot library — vertical list of all templates with status
│   ├── screenshot_overlay.py# Screenshot overlay for region selection
│   └── countdown_overlay.py # 5-second countdown before capture
└── tests/
    ├── test_audio_analyzer_mood_fix.py
    ├── test_audio_capture.py
    ├── test_music2emo_client.py
    ├── test_mood_calibration.py
    ├── test_calibration_popover.py
    └── test_quadrant_chart.py
```

## UI Architecture (Component-based)

The GUI follows a **controller + component** pattern using PySide6:

```
main_window.py (controller)
  ├── theme.py             — design tokens (colors, fonts, spacing, shared QSS)
  ├── icons.py             — SVG icon drawing utility
  ├── sidebar.py           — Sidebar component (play/library/about)
  ├── track_card.py        — Track info card component
  ├── playlist_grid.py     — 5-column playlist grid component
  ├── quadrant_chart.py    — Mood quadrant visualization (QWidget paintEvent)
  ├── calibration_popover.py — 3x3 correction grid dialog (QDialog)
  ├── highlight_overlay.py — Persistent OCR highlight overlay (in-place rect updates)
  ├── spectrum_bar.py      — 16-band FFT spectrum bar
  ├── screenshot_library.py — Template list dialog
  ├── screenshot_overlay.py — Full-screen region selector (QDialog)
  └── countdown_overlay.py  — 5-second countdown before capture
```

**Key principles:**
- `main_window.py` owns all services (OCR, audio, automation) and wires signals — it's the orchestrator, not the UI builder
- Each view component is a focused QWidget subclass with its own QSS, signals, and public API
- `theme.py` is the single source of truth for all colors, sizes, and shared style sheets — never hardcode `#fafafa` or `#5f6368` in component files
- `icons.py` centralizes SVG path data and rendering — components import icon functions instead of drawing paths inline
- Components communicate outward via **Qt Signals** / **callbacks**, never by reaching into sibling components

## Key Implementation Details

### OCR Column Classification

Apple Music playlist view has 4 columns. X center ratio boundaries (relative to screenshot width):

| Column | X Ratio Range |
|--------|--------------|
| Song   | 0.00 – 0.28  |
| Artist | 0.28 – 0.55  |
| Album  | 0.55 – 0.78  |
| Other  | 0.78+        |

Song names are recognized in a single OCR pass. When position templates (`position/song_name`, `position/artist`) exist, only those precise sub-regions are OCR'd instead of the full image.

### Screenshot Region

Default screenshot region ratio: `(0.10, 0.30, 0.98, 0.88)` — left 10%, top 30%, right 98%, bottom 88% of the Apple Music window. Targets the playlist list area, excluding sidebar and top bar.

### Config Format

`config.json` defines playlist hierarchy: volume → mood → playlist name. Each mood entry's `playlist` field is the exact name shown in Apple Music's "Add to Playlist" menu. The `tag` field is one of `VIGOROUS`, `TENSE`, `MELANCHOLY`, `CALM`.

### Action Flow

`ActionExecutor.classify_track()` performs: click three-dots button → wait → **stable-click** "Add to Playlist" (verifies screen has stopped animating by comparing two consecutive screenshots before clicking) → wait → click target playlist name. Each step locates targets via fresh screenshot + template matching, with configurable delays between steps. The stable-click verification only applies to the "Add to Playlist" step.

### Audio Mood Analysis (engine v2)

1. `AudioCaptureManager.start()` — finds Apple Music PID, creates NamedPipe, streams audio via `process-audio-capture`
2. `AudioAnalyzer._analysis_loop()` — sliding window: 10s window (`WINDOW_SECONDS`), 2s hop (`HOP_SECONDS`); each hop captures latest audio, converts stereo→mono, requires ≥ `MIN_AUDIO_SECONDS` (4s) of audio
3. `Music2EmoClient.predict_audio(audio, sr)` — sends binary PCM frame to the engine subprocess (8-byte `struct "<II"` header = sample_rate + frame_count, then float32 mono PCM); engine returns JSON `{valence, arousal}` in 1–9 range. Client handles warmup + single restart-on-crash.
4. Score clamping: model scores clamped to [1, 9] then normalized to [-1, 1] via `(score - 5) / 4` when no calibrator is active.
5. `Calibrator.calibrate(raw_v, raw_a)` — if ≥ `MIN_SAMPLES` (10) personal calibration samples exist, an `IsotonicRegression` per dimension maps raw scores → user-perceived [-1, 1]; otherwise falls back to the default linear `(score - 5) / 4`. Thread-locked (UI thread writes/refits, analyzer thread reads).
6. Quadrant hysteresis: a `QUADRANT_DEADZONE` (0.08) around the axes — a coordinate inside the deadzone keeps the previous quadrant; a real transition requires crossing clearly past the axis.
7. Stabilization: need `STABILIZATION_COUNT` (4) consistent quadrant readings before locking (confidence ≥ `LOCK_CONFIDENCE` 0.6); confidence = consistency×0.6 + boundary_margin×0.4.
8. Boundary detection: if `COORD_HISTORY` (5) consecutive coordinates deviate > `BOUNDARY_THRESHOLD` (0.8, locked: 1.0) from rolling mean → reset analysis with `BOUNDARY_COOLDOWN` (2) frame cooldown (new song detected). Lock mechanism always records quadrant history (even when locked) to allow self-correction.
9. Error handling: if the engine is unavailable, raises, returns an error payload, or returns non-finite scores, the analyzer emits `analysis_error` and returns None for that window (no fake coordinates). A crashed subprocess triggers exactly one `restart()` attempt, then the loop stops.

## Common Pitfalls

- **PaddlePaddle 3.x crash**: `ConvertPirAttribute2RuntimeAttribute` error on Windows. Must use 2.x.
- **PaddleOCR 3.x**: Removed `show_log` parameter, changed `ocr()` to `predict()`. Must use 2.x.
- **Window activation**: May silently fail on Windows. `activate_window()` has a minimize→restore fallback.
- **4K display scaling**: `pygetwindow` may return negative coordinates (e.g., -12) for maximized windows on Windows. This is normal.
- **OCR accuracy**: Leftmost column song names are small and often partially recognized. Position templates (`position/song_name`) mitigate this by OCR'ing a precise sub-region instead of the full image.
- **OCR threading**: PaddleOCR inference runs entirely in a background worker thread (`_capture_and_detect` → `worker`). Never call `OCRReader.read_tracks()` from the main/UI thread — it blocks for 1-3 seconds.
- **Audio capture**: `process-audio-capture` requires Windows 10 2004+ (named pipe support). `AudioCaptureManager` only works when Apple Music is playing audio. WAV header parsing accepts any format (16/24/32-bit int or float, mono/stereo/multi-channel); `_store_pcm` decodes accordingly. Key diagnostics are logged to stderr with `[AUDIO]` prefix.
