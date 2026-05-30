# UI Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the MusicClassifier PySide6 UI to a modern dark flat theme with a 4×4 playlist button grid, one-click classification, and auto-advance workflow.

**Architecture:** Replace the QComboBox dropdown, log panel, and progress bar with a row-based grid (4 volumes × 4 moods). Each playlist is a clickable QPushButton that immediately triggers classification. A start/stop toggle button controls the capture-identify loop. Config data flows from `config.json` → `PlaylistConfig.get_all_moods_flat()` → UI button matrix.

**Tech Stack:** Python 3.12, PySide6, QSS (Qt Style Sheets)

---

### Task 1: Fix config.json to 4 Volumes × 4 Moods

**Files:**
- Modify: `config.json`

- [ ] **Step 1: Rewrite config.json with correct 4-volume structure**

Replace the entire `config.json` with:

```json
{
  "volumes": [
    {
      "name": "风之卷",
      "moods": [
        {"name": "季风", "tag": "VIGOROUS", "playlist": "季风"},
        {"name": "飓风", "tag": "TENSE", "playlist": "飓风"},
        {"name": "秋风", "tag": "MELANCHOLY", "playlist": "秋风"},
        {"name": "轻风", "tag": "CALM", "playlist": "轻风"}
      ]
    },
    {
      "name": "花之卷",
      "moods": [
        {"name": "春化", "tag": "VIGOROUS", "playlist": "春化"},
        {"name": "绽放", "tag": "TENSE", "playlist": "绽放"},
        {"name": "凋零", "tag": "MELANCHOLY", "playlist": "凋零"},
        {"name": "发芽", "tag": "CALM", "playlist": "发芽"}
      ]
    },
    {
      "name": "海之卷",
      "moods": [
        {"name": "碧海", "tag": "VIGOROUS", "playlist": "碧海"},
        {"name": "怒海", "tag": "TENSE", "playlist": "怒海"},
        {"name": "深海", "tag": "MELANCHOLY", "playlist": "深海"},
        {"name": "静海", "tag": "CALM", "playlist": "静海"}
      ]
    },
    {
      "name": "月之卷",
      "moods": [
        {"name": "满月", "tag": "VIGOROUS", "playlist": "满月"},
        {"name": "弦月", "tag": "TENSE", "playlist": "弦月"},
        {"name": "残月", "tag": "MELANCHOLY", "playlist": "残月"},
        {"name": "新月", "tag": "CALM", "playlist": "新月"}
      ]
    }
  ],
  "action_delays": {
    "after_click_ms": 700,
    "before_screenshot_ms": 300,
    "menu_appear_ms": 500
  },
  "apple_music_window_title": "Apple Music"
}
```

- [ ] **Step 2: Commit**

```bash
git add config.json
git commit -m "fix: correct config to 4 volumes with complete moods"
```

---

### Task 2: Update playlist_config Tests for New Config

**Files:**
- Modify: `tests/test_playlist_config.py`

- [ ] **Step 1: Update existing tests and add test for get_all_moods_flat**

Replace the entire `tests/test_playlist_config.py` with:

```python
import json
import tempfile
import pytest
from core.playlist_config import PlaylistConfig


class TestPlaylistConfig:
    def test_load_default_config(self):
        config = PlaylistConfig()
        volumes = config.get_volumes()
        assert len(volumes) == 4
        assert "风之卷" in volumes
        assert "花之卷" in volumes
        assert "海之卷" in volumes
        assert "月之卷" in volumes

    def test_get_moods_for_volume(self):
        config = PlaylistConfig()
        moods = config.get_moods("月之卷")
        assert "新月 (CALM)" in moods
        assert "满月 (VIGOROUS)" in moods

    def test_get_moods_wind_volume(self):
        config = PlaylistConfig()
        moods = config.get_moods("风之卷")
        assert len(moods) == 4
        assert "季风 (VIGOROUS)" in moods
        assert "飓风 (TENSE)" in moods
        assert "秋风 (MELANCHOLY)" in moods
        assert "轻风 (CALM)" in moods

    def test_get_moods_invalid_volume(self):
        config = PlaylistConfig()
        moods = config.get_moods("不存在")
        assert moods == []

    def test_get_playlist_name(self):
        config = PlaylistConfig()
        name = config.get_playlist_name("月之卷", "新月 (CALM)")
        assert name == "新月"

    def test_get_all_moods_flat(self):
        config = PlaylistConfig()
        moods = config.get_all_moods_flat()
        assert len(moods) == 16
        first = moods[0]
        assert first["volume"] == "风之卷"
        assert first["mood_name"] == "季风"
        assert first["tag"] == "VIGOROUS"
        assert first["playlist"] == "季风"
        last = moods[-1]
        assert last["volume"] == "月之卷"
        assert last["mood_name"] == "新月"
        assert last["tag"] == "CALM"
        assert last["playlist"] == "新月"

    def test_get_all_moods_flat_has_all_tags(self):
        config = PlaylistConfig()
        moods = config.get_all_moods_flat()
        tags = {m["tag"] for m in moods}
        assert tags == {"VIGOROUS", "TENSE", "MELANCHOLY", "CALM"}

    def test_load_from_file(self):
        data = {
            "volumes": [
                {
                    "name": "测试卷",
                    "moods": [
                        {"name": "测试情绪", "tag": "TEST", "playlist": "测试歌单"}
                    ]
                }
            ]
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
            path = f.name
        config = PlaylistConfig(path)
        assert config.get_volumes() == ["测试卷"]
        assert config.get_moods("测试卷") == ["测试情绪 (TEST)"]
```

- [ ] **Step 2: Run tests to verify they fail (get_all_moods_flat not yet implemented)**

Run: `python -m pytest tests/test_playlist_config.py -v`
Expected: FAIL on `test_get_all_moods_flat` and `test_get_all_moods_flat_has_all_tags` with `AttributeError: 'PlaylistConfig' object has no attribute 'get_all_moods_flat'`. The `test_load_default_config` should now pass (expects 4 volumes). Other existing tests should pass.

- [ ] **Step 3: Commit**

```bash
git add tests/test_playlist_config.py
git commit -m "test: update playlist_config tests for 4 volumes and add get_all_moods_flat tests"
```

---

### Task 3: Add get_all_moods_flat to PlaylistConfig

**Files:**
- Modify: `core/playlist_config.py`

- [ ] **Step 1: Add the get_all_moods_flat method**

Add the following method to the `PlaylistConfig` class, after the `get_all_playlists` method (after line 42):

```python
    def get_all_moods_flat(self) -> list[dict]:
        result = []
        for v in self._data.get("volumes", []):
            for m in v.get("moods", []):
                result.append({
                    "volume": v["name"],
                    "mood_name": m["name"],
                    "tag": m["tag"],
                    "playlist": m["playlist"],
                })
        return result
```

- [ ] **Step 2: Run all tests to verify they pass**

Run: `python -m pytest tests/test_playlist_config.py -v`
Expected: All 8 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add core/playlist_config.py
git commit -m "feat: add get_all_moods_flat method to PlaylistConfig"
```

---

### Task 4: Rewrite MainWindow UI

**Files:**
- Modify: `gui/main_window.py`

This task replaces the entire `_init_ui` method, updates imports, adds QSS styling, rewrites `_on_classify` to use button data instead of dropdown, adds start/stop toggle, and removes log/progress handlers.

- [ ] **Step 1: Rewrite the entire gui/main_window.py**

Replace the entire file with:

```python
import threading
from functools import partial
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QMessageBox,
)
from PySide6.QtCore import Signal, QObject, Qt
from core.models import TrackInfo, ClassificationResult
from core.screen_capture import ScreenCapture
from core.ocr_reader import OCRReader
from core.action_executor import ActionExecutor
from core.playlist_config import PlaylistConfig


DARK_QSS = """
QMainWindow, QWidget {
    background-color: #1a1a2e;
    color: #e0e0e0;
}
QLabel {
    color: #e0e0e0;
}
QLabel#track_name {
    font-size: 16px;
    font-weight: bold;
    color: #ffffff;
}
QLabel#album_name {
    font-size: 12px;
    color: #888888;
}
QLabel#volume_label {
    font-size: 11px;
    font-weight: bold;
    color: #e94560;
}
QLabel#tag_header {
    font-size: 10px;
    color: #666666;
}
QPushButton#playlist_btn {
    background-color: #0f3460;
    color: #e0e0e0;
    border: none;
    border-radius: 5px;
    padding: 10px 8px;
    font-size: 13px;
    min-height: 20px;
}
QPushButton#playlist_btn:hover {
    background-color: #1a4a7a;
}
QPushButton#playlist_btn:pressed {
    background-color: #e94560;
}
QPushButton#playlist_btn:disabled {
    background-color: #16213e;
    color: #444444;
}
QPushButton#start_btn {
    background-color: #e94560;
    color: #ffffff;
    border: none;
    border-radius: 5px;
    padding: 10px 16px;
    font-size: 14px;
    font-weight: bold;
    min-height: 20px;
}
QPushButton#start_btn:hover {
    background-color: #ff6b81;
}
QPushButton#start_btn:checked {
    background-color: #c0392b;
}
QPushButton#action_btn {
    background-color: #533483;
    color: #e0e0e0;
    border: none;
    border-radius: 5px;
    padding: 10px 16px;
    font-size: 13px;
    min-height: 20px;
}
QPushButton#action_btn:hover {
    background-color: #6c45a3;
}
QPushButton#action_btn:disabled {
    background-color: #2a1a43;
    color: #444444;
}
"""


class Signals(QObject):
    track_detected = Signal(object)
    classification_done = Signal(object)
    error_occurred = Signal(str)


class MainWindow(QMainWindow):
    def __init__(self, config: PlaylistConfig):
        super().__init__()
        self._config = config
        self._signals = Signals()
        self._screen_capture = ScreenCapture(config.window_title)
        self._ocr_reader = OCRReader()
        self._action_executor = ActionExecutor(
            self._screen_capture,
            self._ocr_reader,
            after_click_ms=config.after_click_ms,
            menu_appear_ms=config.menu_appear_ms,
        )
        self._current_track: TrackInfo | None = None
        self._running = False
        self._playlist_buttons: list[QPushButton] = []
        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        self.setWindowTitle("MusicClassifier")
        self.setMinimumSize(520, 480)
        self.setStyleSheet(DARK_QSS)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        self._track_label = QLabel("等待识别...")
        self._track_label.setObjectName("track_name")
        main_layout.addWidget(self._track_label)

        self._album_label = QLabel("")
        self._album_label.setObjectName("album_name")
        main_layout.addWidget(self._album_label)

        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setSpacing(6)
        grid.setContentsMargins(0, 8, 0, 8)

        tags = ["VIGOROUS", "TENSE", "MELANCHOLY", "CALM"]
        grid.addWidget(QLabel(""), 0, 0)
        for col, tag in enumerate(tags, start=1):
            header = QLabel(tag)
            header.setObjectName("tag_header")
            header.setAlignment(Qt.AlignCenter)
            grid.addWidget(header, 0, col)

        moods = self._config.get_all_moods_flat()
        volumes_seen: list[str] = []
        for mood in moods:
            vol = mood["volume"]
            if vol not in volumes_seen:
                volumes_seen.append(vol)

        for row_idx, volume_name in enumerate(volumes_seen, start=1):
            vol_label = QLabel(volume_name)
            vol_label.setObjectName("volume_label")
            vol_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            grid.addWidget(vol_label, row_idx, 0)

            vol_moods = [m for m in moods if m["volume"] == volume_name]
            for col_idx, mood_info in enumerate(vol_moods, start=1):
                btn = QPushButton(mood_info["mood_name"])
                btn.setObjectName("playlist_btn")
                btn.setEnabled(False)
                btn.setProperty("playlist_name", mood_info["playlist"])
                btn.clicked.connect(partial(self._on_classify, mood_info["playlist"]))
                self._playlist_buttons.append(btn)
                grid.addWidget(btn, row_idx, col_idx)

        main_layout.addWidget(grid_widget)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self._start_btn = QPushButton("开始")
        self._start_btn.setObjectName("start_btn")
        self._start_btn.setCheckable(True)
        self._start_btn.clicked.connect(self._on_start_toggle)
        btn_layout.addWidget(self._start_btn)

        self._skip_btn = QPushButton("跳过")
        self._skip_btn.setObjectName("action_btn")
        self._skip_btn.setEnabled(False)
        self._skip_btn.clicked.connect(self._on_skip)
        btn_layout.addWidget(self._skip_btn)

        self._recapture_btn = QPushButton("重新截图")
        self._recapture_btn.setObjectName("action_btn")
        self._recapture_btn.setEnabled(False)
        self._recapture_btn.clicked.connect(self._on_recapture)
        btn_layout.addWidget(self._recapture_btn)

        main_layout.addLayout(btn_layout)

    def _connect_signals(self):
        self._signals.track_detected.connect(self._handle_track_detected)
        self._signals.classification_done.connect(self._handle_classification_done)
        self._signals.error_occurred.connect(self._handle_error)

    def _on_start_toggle(self):
        if self._start_btn.isChecked():
            if not self._screen_capture.find_window():
                QMessageBox.warning(self, "错误", "未找到 Apple Music 窗口，请先打开 Apple Music。")
                self._start_btn.setChecked(False)
                return
            self._screen_capture.activate_window()
            self._start_btn.setText("停止")
            self._running = True
            self._set_playlist_buttons_enabled(False)
            self._skip_btn.setEnabled(True)
            self._recapture_btn.setEnabled(True)
            self._capture_and_detect()
        else:
            self._start_btn.setText("开始")
            self._running = False
            self._set_playlist_buttons_enabled(False)
            self._skip_btn.setEnabled(False)
            self._recapture_btn.setEnabled(False)

    def _set_playlist_buttons_enabled(self, enabled: bool):
        for btn in self._playlist_buttons:
            btn.setEnabled(enabled)

    def _capture_and_detect(self):
        if not self._running:
            return

        def worker():
            self._screen_capture.activate_window()
            image = self._screen_capture.capture_list_region(delay_ms=self._config.before_screenshot_ms)
            if image is None:
                self._signals.error_occurred.emit("截图失败，请确认 Apple Music 窗口可见")
                return
            offset = self._screen_capture._window_rect[:2] if self._screen_capture._window_rect else (0, 0)
            tracks = self._ocr_reader.read_tracks(image, offset)
            if not tracks:
                self._signals.error_occurred.emit("OCR 未识别到歌曲，请确认歌单列表可见")
                return
            self._signals.track_detected.emit(tracks[0])

        threading.Thread(target=worker, daemon=True).start()

    def _handle_track_detected(self, track: TrackInfo):
        self._current_track = track
        self._track_label.setText(track.display_text())
        self._album_label.setText(f"专辑: {track.album}" if track.album else "")
        self._set_playlist_buttons_enabled(True)

    def _on_classify(self, playlist_name: str):
        if not self._current_track:
            return
        track = self._current_track
        self._set_playlist_buttons_enabled(False)
        self._skip_btn.setEnabled(False)
        self._recapture_btn.setEnabled(False)

        def worker():
            result = self._action_executor.classify_track(
                track.dots_btn_pos, playlist_name, track.song_name
            )
            self._signals.classification_done.emit(result)

        threading.Thread(target=worker, daemon=True).start()

    def _handle_classification_done(self, result: ClassificationResult):
        self._set_playlist_buttons_enabled(True)
        self._skip_btn.setEnabled(True)
        self._recapture_btn.setEnabled(True)
        self._capture_and_detect()

    def _on_skip(self):
        self._capture_and_detect()

    def _on_recapture(self):
        self._capture_and_detect()

    def _handle_error(self, msg: str):
        self._track_label.setText(f"错误: {msg}")
        self._set_playlist_buttons_enabled(True)
        self._skip_btn.setEnabled(True)
        self._recapture_btn.setEnabled(True)
```

- [ ] **Step 2: Run all existing tests to verify no regressions**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS (UI code has no dedicated tests; core tests are unaffected).

- [ ] **Step 3: Manual verification — launch the app and check UI**

Run: `python main.py`

Verify visually:
1. Window has dark background (#1a1a2e)
2. Top shows "等待识别..." placeholder
3. 4×4 grid of playlist buttons with volume labels on left and tag headers on top
4. Buttons are disabled (grayed out) initially
5. "开始" button is red, "跳过" and "重新截图" are purple and disabled
6. Window title is "MusicClassifier"
7. No log panel or progress bar visible

- [ ] **Step 4: Commit**

```bash
git add gui/main_window.py
git commit -m "feat: rewrite UI with dark flat theme and 4x4 playlist button grid"
```

---

### Task 5: Add .superpowers to .gitignore

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Append .superpowers/ to .gitignore**

Add the following line to the end of `.gitignore`:

```
.superpowers/
```

- [ ] **Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: add .superpowers/ to .gitignore"
```
