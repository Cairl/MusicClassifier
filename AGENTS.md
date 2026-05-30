# AGENTS.md

## Project Overview

MusicClassifier is a Windows-based semi-automated Apple Music song classification tool. It captures the Apple Music window, recognizes song names via OCR (PaddleOCR), lets the user click a target playlist button, and automatically performs mouse clicks to add the song to the playlist.

**Architecture**: Screenshot → OCR recognition → User selection → Simulated mouse clicks. Four core modules are connected through the `TrackInfo` dataclass. All UI automation runs on background threads to keep the PySide6 GUI responsive.

**Tech Stack**: Python 3.12, PySide6, PaddleOCR 2.x, PaddlePaddle 2.x, PyAutoGUI, pygetwindow, OpenCV

## Setup Commands

- Install dependencies: `pip install -r requirements.txt`
- **Critical**: PaddlePaddle 3.x and PaddleOCR 3.x are incompatible with this project. Version constraints in `requirements.txt` are `paddleocr>=2.7,<3.0` and `paddlepaddle>=2.5,<3.0`. Do not upgrade beyond these ranges.
- Python path on this machine: `C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe`

## Development Workflow

- Run the application: `python main.py`
- The app requires Apple Music to be open on Windows. It finds the window by title "Apple Music" (configurable in `config.json`).
- Before taking a screenshot, the app automatically activates and brings the Apple Music window to the foreground.

## Testing Instructions

- Run all tests: `python -m pytest tests/ -v`
- Run a single test file: `python -m pytest tests/test_models.py -v`
- Tests are located in `tests/`, named `test_<module_name>.py`
- 44 tests across 4 test files
- Tests use `unittest.mock` to mock `pygetwindow`, `pyautogui`, and `PaddleOCR`. No real windows or OCR needed.

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
- Sidebar (48px): white background + 1px `#e8eaed` separator; play button at top, menu button at bottom
- Sidebar icon buttons: 32×32 transparent background + `#5f6368` icons, hover shows `#e8eaed` circle, MD3 Filled Tonal style
- Main area: track info card (12px rounded, no border, light shadow) → mood tag row → 5-column playlist grid (volume name + VIGOROUS/TENSE/MELANCHOLY/CALM)
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
│   └── template_library.py  # Template collection, matching, and missing detection
├── gui/
│   ├── main_window.py       # PySide6 main window, MD3 sidebar + 5-column playlist grid
│   ├── icon_button.py       # Rounded rectangle icon button (QToolButton + QIcon)
│   ├── settings_popover.py  # Settings popover menu (template capture / about)
│   ├── capture_wizard.py    # Template capture wizard
│   └── screenshot_overlay.py # Screenshot overlay for region selection
└── tests/
    ├── test_models.py
    ├── test_ocr_reader.py
    ├── test_playlist_config.py
    ├── test_screen_capture.py
    ├── test_action_executor.py
    └── test_template_library.py
```

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

`ActionExecutor.classify_track()` performs: click three-dots button → wait → click "Add to Playlist" → wait → click target playlist name. Each step locates targets via fresh screenshot + OCR, with configurable delays between steps.

## Common Pitfalls

- **PaddlePaddle 3.x crash**: `ConvertPirAttribute2RuntimeAttribute` error on Windows. Must use 2.x.
- **PaddleOCR 3.x**: Removed `show_log` parameter, changed `ocr()` to `predict()`. Must use 2.x.
- **Window activation**: May silently fail on Windows. `activate_window()` has a minimize→restore fallback.
- **4K display scaling**: `pygetwindow` may return negative coordinates (e.g., -12) for maximized windows on Windows. This is normal.
- **OCR accuracy**: Leftmost column song names are small and often partially recognized. The two-pass OCR (full image + 3x upscaled song region) mitigates this but is not perfect.
