# AGENTS.md

## Project Overview

MusicClassifier is a Windows-based semi-automated Apple Music song classification tool. It captures the Apple Music window, recognizes song names via OCR (PaddleOCR), lets the user click a target playlist button, and automatically performs mouse clicks to add the song to the playlist.

**Architecture**: Screenshot → OCR recognition → User selection → Simulated mouse clicks. Four core modules are connected through the `TrackInfo` dataclass. All UI automation runs on background threads to keep the PySide6 GUI responsive.

Additionally, the app features a **real-time audio mood analysis** system: it captures process audio from Apple Music via named pipes, extracts features using librosa (RMS, tempo, spectral centroid, bandwidth, ZCR, harmonic ratio), maps them to a valence-arousal quadrant, and recommends the best matching playlist.

**Tech Stack**: Python 3.12, PySide6, PaddleOCR 2.x, PaddlePaddle 2.x, PyAutoGUI, pygetwindow, OpenCV, librosa, process-audio-capture

## Setup Commands

- Install dependencies: `pip install -r requirements.txt`
- **Critical**: PaddlePaddle 3.x and PaddleOCR 3.x are incompatible with this project. Version constraints in `requirements.txt` are `paddleocr>=2.7,<3.0` and `paddlepaddle>=2.5,<3.0`. Do not upgrade beyond these ranges.
- Python path on this machine: `C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe`

## Development Workflow

- Run the application: `python main.py`
- **Mood detection starts automatically on launch** (no toggle switch needed)
- The app requires Apple Music to be open on Windows. It finds the window by title "Apple Music" (configurable in `config.json`).
- Before taking a screenshot, the app automatically activates and brings the Apple Music window to the foreground.
- Quadrant chart is always visible, showing "等待音频..." when idle

## Testing Instructions

- Run all tests: `python -m pytest tests/ -v`
- Tests are located in `tests/`, named `test_<module_name>.py`
- 3 test files covering audio analyzer (including temporal smoothing, boundary detection, confidence, and instrument-specific scenarios), audio capture manager, and quadrant chart.
- Tests use `unittest.mock` to mock `pyautogui`, `pygetwindow`, `PaddleOCR`, and `librosa`. No real windows or OCR needed.

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
|- Sidebar (48px): white background + 1px `#e8eaed` separator; play button at top, library and about buttons at bottom
|- Main area: track info card (song name + album, 12px rounded, no border) → mood status bar → quadrant chart → 5-column playlist grid
- Window width fixed at 240 (DPI-scaled), height adapts to content
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
│   └── audio_analyzer.py    # librosa feature extraction + valence-arousal mood analysis
├── gui/
│   ├── main_window.py       # Main window controller — assembles components, wires signals
│   ├── theme.py             # Design system — color tokens, typography, spacing, shared QSS
│   ├── icons.py             # SVG path icon utilities (play, library, about)
│   ├── sidebar.py           # Sidebar component — play / library / about buttons
│   ├── track_card.py        # Track info card — song name, album
│   ├── playlist_grid.py     # Playlist button grid — 5-column grid from config
│   ├── quadrant_chart.py    # Valence-arousal quadrant visualization
│   ├── screenshot_library.py# Screenshot library — vertical list of all templates with ✓/✗ status
│   ├── screenshot_overlay.py# Screenshot overlay for region selection
│   ├── countdown_overlay.py # 5-second countdown before capture
│   └── icons.py             # SVG path icon utilities
└── tests/
    ├── test_audio_analyzer.py
    ├── test_audio_capture.py
    └── test_quadrant_chart.py
```

## UI Architecture (Component-based)

The GUI follows a **controller + component** pattern using PySide6:

```
main_window.py (controller)
  ├── theme.py       — design tokens (colors, fonts, spacing, shared QSS)
  ├── icons.py       — SVG icon drawing utility
  ├── sidebar.py     — Sidebar component (play/record/settings)
  ├── track_card.py  — Track info card component
  ├── playlist_grid.py — 5-column playlist grid component
  ├── quadrant_chart.py — Mood quadrant visualization (QWidget paintEvent)
  ├── settings_popover.py — Popup menu (standalone QWidget)
  ├── capture_wizard.py — Template capture dialog (QDialog)
  └── screenshot_overlay.py — Full-screen region selector (QDialog)
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

Song names are refined by a second OCR pass: crop the left 30% of the image and upscale 3x before re-recognizing.

### Screenshot Region

Default screenshot region ratio: `(0.10, 0.30, 0.98, 0.88)` — left 10%, top 30%, right 98%, bottom 88% of the Apple Music window. Targets the playlist list area, excluding sidebar and top bar.

### Config Format

`config.json` defines playlist hierarchy: volume → mood → playlist name. Each mood entry's `playlist` field is the exact name shown in Apple Music's "Add to Playlist" menu. The `tag` field is one of `VIGOROUS`, `TENSE`, `MELANCHOLY`, `CALM`.

### Action Flow

`ActionExecutor.classify_track()` performs: click three-dots button → wait → **stable-click** "Add to Playlist" (verifies screen has stopped animating by comparing two consecutive screenshots before clicking) → wait → click target playlist name. Each step locates targets via fresh screenshot + template matching, with configurable delays between steps. The stable-click verification only applies to the "Add to Playlist" step.

### Audio Mood Analysis

1. `AudioCaptureManager.start()` — finds Apple Music PID, creates NamedPipe, streams audio via `process-audio-capture`
2. `AudioAnalyzer._analysis_loop()` — every 3s captures latest N seconds of stereo audio → converts to mono
3. `_extract_features()` — computes RMS, tempo, spectral centroid, bandwidth, ZCR, harmonic ratio, spectral contrast, spectral flatness, onset strength (log-compressed to dampen transient-heavy instruments like piano), spectral rolloff, MFCC (13 coefficients); normalizes each to [0,1]
4. `_apply_temporal_smoothing()` — EMA filter (α=0.35) over a 5-frame buffer to reduce inter-frame feature jitter
5. `_map_to_quadrant()` — arousal = `tempo×0.35 + RMS×0.25 + bandwidth×0.10 + onset×0.15 + rolloff×0.15`; valence = `contrast×0.30 + centroid×0.15 + harmonic×0.20 + rolloff×0.15 - RMS×0.10 - ZCR×0.05 - flatness×0.05`; tempo is the dominant arousal driver to prevent piano/strings bandwidth from causing false high-energy readings
6. Stabilization: need 4 consistent quadrant readings before locking (confidence ≥ 60%); confidence = consistency×0.6 + boundary_margin×0.4 (distance from axes)
7. Boundary detection: if 5 consecutive coordinates deviate > 0.8 (locked: 1.2) from rolling mean → reset analysis with 2-frame cooldown (new song detected)

## Common Pitfalls

- **PaddlePaddle 3.x crash**: `ConvertPirAttribute2RuntimeAttribute` error on Windows. Must use 2.x.
- **PaddleOCR 3.x**: Removed `show_log` parameter, changed `ocr()` to `predict()`. Must use 2.x.
- **Window activation**: May silently fail on Windows. `activate_window()` has a minimize→restore fallback.
- **4K display scaling**: `pygetwindow` may return negative coordinates (e.g., -12) for maximized windows on Windows. This is normal.
- **OCR accuracy**: Leftmost column song names are small and often partially recognized. The two-pass OCR (full image + 3x upscaled song region) mitigates this but is not perfect.
- **Audio capture**: `process-audio-capture` requires Windows 10 2004+ (named pipe support). `AudioCaptureManager` only works when Apple Music is playing audio.
