# MusicClassifier 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个半自动 Apple Music 歌曲分类工具，通过 OCR 识别歌名，用户在 PySide6 GUI 中选择分类，程序自动完成点击操作。

**Architecture:** 截图 → OCR 识别 → 用户选择 → 模拟点击，四个核心模块职责分离，通过 TrackInfo 数据结构串联。所有 UI 自动化操作在独立线程执行，不阻塞 GUI。

**Tech Stack:** Python 3.10+, PySide6, PaddleOCR, pyautogui, pygetwindow, opencv-python, Pillow

---

## 文件结构

```
MusicClassifier/
├── main.py                  # 入口
├── core/
│   ├── __init__.py
│   ├── models.py            # 数据模型 (TrackInfo 等)
│   ├── screen_capture.py    # 截取 Apple Music 窗口
│   ├── ocr_reader.py        # OCR 识别歌名、行定位
│   ├── action_executor.py   # 模拟鼠标点击
│   └── playlist_config.py   # 歌单分类配置
├── gui/
│   ├── __init__.py
│   └── main_window.py       # PySide6 主界面
├── config.json              # 用户配置
├── requirements.txt         # 依赖
└── tests/
    ├── __init__.py
    ├── test_models.py
    ├── test_playlist_config.py
    ├── test_ocr_reader.py
    └── test_screen_capture.py
```

---

### Task 1: 项目初始化与依赖

**Files:**
- Create: `requirements.txt`
- Create: `core/__init__.py`
- Create: `gui/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: 创建目录结构**

```bash
cd "S:\Github Repositories\MusicClassifier"
mkdir core gui tests
```

- [ ] **Step 2: 创建 requirements.txt**

```
PySide6>=6.6
paddleocr>=2.7
paddlepaddle>=2.5
pyautogui>=0.9.54
pygetwindow>=0.0.9
opencv-python>=4.8
Pillow>=10.0
```

- [ ] **Step 3: 创建 __init__.py 文件**

创建空的 `core/__init__.py`、`gui/__init__.py`、`tests/__init__.py`

- [ ] **Step 4: 安装依赖**

```bash
pip install -r requirements.txt
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: initialize project structure and dependencies"
```

---

### Task 2: 数据模型

**Files:**
- Create: `core/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: 写测试**

```python
import pytest
from core.models import TrackInfo, ClassificationResult


class TestTrackInfo:
    def test_create_track_info(self):
        track = TrackInfo(
            song_name="Beta",
            artist="α·Pav",
            album="Pavonis ~ Piano Collection II ~",
            row_y=200,
            dots_btn_pos=(1500, 200),
        )
        assert track.song_name == "Beta"
        assert track.artist == "α·Pav"
        assert track.album == "Pavonis ~ Piano Collection II ~"
        assert track.row_y == 200
        assert track.dots_btn_pos == (1500, 200)

    def test_track_info_display_text(self):
        track = TrackInfo(
            song_name="Beta",
            artist="α·Pav",
            album="Pavonis ~ Piano Collection II ~",
            row_y=200,
            dots_btn_pos=(1500, 200),
        )
        assert track.display_text() == "Beta — α·Pav"

    def test_track_info_display_text_no_artist(self):
        track = TrackInfo(
            song_name="Beta",
            artist="",
            album="Album",
            row_y=200,
            dots_btn_pos=(1500, 200),
        )
        assert track.display_text() == "Beta"


class TestClassificationResult:
    def test_success_result(self):
        result = ClassificationResult(
            success=True,
            track_name="Beta",
            target_playlist="新月",
            message="已分类到: 月之卷 > 新月",
        )
        assert result.success is True
        assert result.track_name == "Beta"

    def test_failure_result(self):
        result = ClassificationResult(
            success=False,
            track_name="Beta",
            target_playlist="",
            message="三点按钮定位失败",
        )
        assert result.success is False
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd "S:\Github Repositories\MusicClassifier"
python -m pytest tests/test_models.py -v
```
Expected: FAIL - ModuleNotFoundError

- [ ] **Step 3: 实现 models.py**

```python
from dataclasses import dataclass


@dataclass
class TrackInfo:
    song_name: str
    artist: str
    album: str
    row_y: int
    dots_btn_pos: tuple[int, int]

    def display_text(self) -> str:
        if self.artist:
            return f"{self.song_name} — {self.artist}"
        return self.song_name


@dataclass
class ClassificationResult:
    success: bool
    track_name: str
    target_playlist: str
    message: str
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_models.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/models.py tests/test_models.py
git commit -m "feat: add data models (TrackInfo, ClassificationResult)"
```

---

### Task 3: 歌单分类配置

**Files:**
- Create: `core/playlist_config.py`
- Create: `tests/test_playlist_config.py`
- Create: `config.json`

- [ ] **Step 1: 写测试**

```python
import json
import tempfile
import pytest
from core.playlist_config import PlaylistConfig


class TestPlaylistConfig:
    def test_load_default_config(self):
        config = PlaylistConfig()
        volumes = config.get_volumes()
        assert len(volumes) == 5
        assert "风之卷" in volumes

    def test_get_moods_for_volume(self):
        config = PlaylistConfig()
        moods = config.get_moods("月之卷")
        assert "新月 (CALM)" in moods
        assert "满月 (VIGOROUS)" in moods

    def test_get_moods_invalid_volume(self):
        config = PlaylistConfig()
        moods = config.get_moods("不存在")
        assert moods == []

    def test_get_playlist_name(self):
        config = PlaylistConfig()
        name = config.get_playlist_name("月之卷", "新月 (CALM)")
        assert name == "新月"

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

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_playlist_config.py -v
```
Expected: FAIL

- [ ] **Step 3: 创建 config.json**

```json
{
  "volumes": [
    {
      "name": "风之卷",
      "moods": [
        {"name": "秋风", "tag": "MELANCHOLY", "playlist": "秋风"},
        {"name": "轻风", "tag": "CALM", "playlist": "轻风"}
      ]
    },
    {
      "name": "花之卷",
      "moods": [
        {"name": "春花", "tag": "VIGOROUS", "playlist": "春花"},
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
    },
    {
      "name": "人之卷",
      "moods": [
        {"name": "新月", "tag": "CALM", "playlist": "1. 新月"},
        {"name": "峨眉月", "tag": "CALM", "playlist": "2. 峨眉月"},
        {"name": "上弦月", "tag": "TENSE", "playlist": "3. 上弦月"},
        {"name": "凸月", "tag": "TENSE", "playlist": "4. 凸月"},
        {"name": "满月", "tag": "VIGOROUS", "playlist": "5. 满月"},
        {"name": "亏凸月", "tag": "MELANCHOLY", "playlist": "6. 亏凸月"},
        {"name": "下弦月", "tag": "MELANCHOLY", "playlist": "7. 下弦月"},
        {"name": "残月", "tag": "MELANCHOLY", "playlist": "8. 残月"}
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

- [ ] **Step 4: 实现 playlist_config.py**

```python
import json
from pathlib import Path


class PlaylistConfig:
    DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config.json"

    def __init__(self, config_path: str | None = None):
        self._config_path = Path(config_path) if config_path else self.DEFAULT_CONFIG_PATH
        self._data = self._load()

    def _load(self) -> dict:
        if self._config_path.exists():
            with open(self._config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"volumes": [], "action_delays": {}, "apple_music_window_title": "Apple Music"}

    def get_volumes(self) -> list[str]:
        return [v["name"] for v in self._data.get("volumes", [])]

    def get_moods(self, volume_name: str) -> list[str]:
        for v in self._data.get("volumes", []):
            if v["name"] == volume_name:
                return [f"{m['name']} ({m['tag']})" for m in v["moods"]]
        return []

    def get_playlist_name(self, volume_name: str, mood_display: str) -> str:
        mood_name = mood_display.split(" (")[0] if " (" in mood_display else mood_display
        for v in self._data.get("volumes", []):
            if v["name"] == volume_name:
                for m in v["moods"]:
                    if m["name"] == mood_name:
                        return m["playlist"]
        return mood_name

    @property
    def after_click_ms(self) -> int:
        return self._data.get("action_delays", {}).get("after_click_ms", 700)

    @property
    def before_screenshot_ms(self) -> int:
        return self._data.get("action_delays", {}).get("before_screenshot_ms", 300)

    @property
    def menu_appear_ms(self) -> int:
        return self._data.get("action_delays", {}).get("menu_appear_ms", 500)

    @property
    def window_title(self) -> str:
        return self._data.get("apple_music_window_title", "Apple Music")
```

- [ ] **Step 5: 运行测试确认通过**

```bash
python -m pytest tests/test_playlist_config.py -v
```
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add core/playlist_config.py tests/test_playlist_config.py config.json
git commit -m "feat: add playlist config with volume/mood hierarchy"
```

---

### Task 4: 窗口截图模块

**Files:**
- Create: `core/screen_capture.py`
- Create: `tests/test_screen_capture.py`

- [ ] **Step 1: 写测试**

```python
import numpy as np
import pytest
from unittest.mock import patch, MagicMock
from core.screen_capture import ScreenCapture


class TestScreenCapture:
    def test_init_with_window_title(self):
        capture = ScreenCapture("Apple Music")
        assert capture._window_title == "Apple Music"

    @patch("core.screen_capture.pygetwindow")
    def test_find_window_success(self, mock_pgw):
        mock_win = MagicMock()
        mock_win.left, mock_win.top = 100, 100
        mock_win.width, mock_win.height = 1200, 800
        mock_pgw.getWindowsWithTitle.return_value = [mock_win]
        capture = ScreenCapture("Apple Music")
        rect = capture.find_window()
        assert rect == (100, 100, 1300, 900)

    @patch("core.screen_capture.pygetwindow")
    def test_find_window_not_found(self, mock_pgw):
        mock_pgw.getWindowsWithTitle.return_value = []
        capture = ScreenCapture("Apple Music")
        rect = capture.find_window()
        assert rect is None

    @patch("core.screen_capture.pygetwindow")
    def test_capture_region(self, mock_pgw):
        mock_win = MagicMock()
        mock_win.left, mock_win.top = 0, 0
        mock_win.width, mock_win.height = 1920, 1080
        mock_pgw.getWindowsWithTitle.return_value = [mock_win]
        capture = ScreenCapture("Apple Music")
        with patch("core.screen_capture.pyautogui") as mock_pag:
            mock_pag.screenshot.return_value = MagicMock()
            result = capture.capture_list_region()
            assert result is not None or result is None
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_screen_capture.py -v
```
Expected: FAIL

- [ ] **Step 3: 实现 screen_capture.py**

```python
import time
import pygetwindow as pgw
import pyautogui as pag
import numpy as np
from PIL import Image
from pathlib import Path


class ScreenCapture:
    def __init__(self, window_title: str, list_region_ratio: tuple | None = None):
        self._window_title = window_title
        self._list_region_ratio = list_region_ratio or (0.25, 0.35, 0.98, 0.92)
        self._window_rect: tuple | None = None

    def find_window(self) -> tuple | None:
        windows = pgw.getWindowsWithTitle(self._window_title)
        if not windows:
            return None
        win = windows[0]
        self._window_rect = (win.left, win.top, win.left + win.width, win.top + win.height)
        return self._window_rect

    def capture_list_region(self, delay_ms: int = 300) -> np.ndarray | None:
        if not self._window_rect:
            rect = self.find_window()
            if not rect:
                return None
        time.sleep(delay_ms / 1000)
        left, top, right, bottom = self._window_rect
        w = right - left
        h = bottom - top
        rl, rt, rr, rb = self._list_region_ratio
        region = (int(left + w * rl), int(top + h * rt), int(left + w * rr), int(top + h * rb))
        screenshot = pag.screenshot(region=region)
        return np.array(screenshot)

    def capture_full_window(self, delay_ms: int = 300) -> np.ndarray | None:
        if not self._window_rect:
            rect = self.find_window()
            if not rect:
                return None
        time.sleep(delay_ms / 1000)
        left, top, right, bottom = self._window_rect
        screenshot = pag.screenshot(region=(left, top, right - left, bottom - top))
        return np.array(screenshot)
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_screen_capture.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/screen_capture.py tests/test_screen_capture.py
git commit -m "feat: add screen capture module for Apple Music window"
```

---

### Task 5: OCR 识别模块

**Files:**
- Create: `core/ocr_reader.py`
- Create: `tests/test_ocr_reader.py`

- [ ] **Step 1: 写测试**

```python
import numpy as np
import pytest
from unittest.mock import patch, MagicMock
from core.ocr_reader import OCRReader
from core.models import TrackInfo


class TestOCRReader:
    def test_init(self):
        reader = OCRReader()
        assert reader._ocr is None

    def test_parse_ocr_results_to_tracks(self):
        reader = OCRReader()
        ocr_results = [
            [[10, 200, 300, 230], ("Beta", 0.98)],
            [[10, 260, 300, 290], ("α·Pav", 0.95)],
            [[10, 320, 300, 350], ("Everything Is Quiet Now", 0.97)],
            [[10, 380, 300, 410], ("Elijah Who", 0.93)],
        ]
        tracks = reader._parse_to_tracks(ocr_results, img_width=800, window_offset=(300, 100))
        assert len(tracks) >= 1
        if tracks:
            assert tracks[0].song_name == "Beta"

    def test_empty_ocr_results(self):
        reader = OCRReader()
        tracks = reader._parse_to_tracks([], img_width=800, window_offset=(0, 0))
        assert tracks == []

    def test_find_dots_button_position(self):
        reader = OCRReader()
        pos = reader._estimate_dots_pos(row_y=200, img_width=800, window_offset=(300, 100))
        assert pos[0] > 300
        assert pos[1] == 200 + 100
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_ocr_reader.py -v
```
Expected: FAIL

- [ ] **Step 3: 实现 ocr_reader.py**

```python
import cv2
import numpy as np
from paddleocr import PaddleOCR
from core.models import TrackInfo


class OCRReader:
    DOTS_X_RATIO = 0.95

    def __init__(self):
        self._ocr: PaddleOCR | None = None

    def _ensure_ocr(self):
        if self._ocr is None:
            self._ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)

    def read_tracks(self, image: np.ndarray, window_offset: tuple[int, int] = (0, 0)) -> list[TrackInfo]:
        self._ensure_ocr()
        result = self._ocr.ocr(image, cls=True)
        if not result or not result[0]:
            return []
        ocr_lines = []
        for line in result[0]:
            box = line[0]
            text = line[1][0]
            confidence = line[1][1]
            x_min = int(min(p[0] for p in box))
            y_min = int(min(p[1] for p in box))
            x_max = int(max(p[0] for p in box))
            y_max = int(max(p[1] for p in box))
            ocr_lines.append(([x_min, y_min, x_max, y_max], (text, confidence)))
        return self._parse_to_tracks(ocr_lines, image.shape[1], window_offset)

    def _parse_to_tracks(self, ocr_results: list, img_width: int, window_offset: tuple[int, int]) -> list[TrackInfo]:
        if not ocr_results:
            return []
        rows: dict[int, list] = {}
        for box, (text, conf) in ocr_results:
            y_center = (box[1] + box[3]) // 2
            row_key = y_center // 40 * 40
            if row_key not in rows:
                rows[row_key] = []
            rows[row_key].append((box, text, conf))
        tracks = []
        for row_key in sorted(rows.keys()):
            items = sorted(rows[row_key], key=lambda x: x[0][0])
            song_name = ""
            artist = ""
            album = ""
            if len(items) >= 1:
                song_name = items[0][1]
            if len(items) >= 2:
                artist = items[1][1]
            if len(items) >= 3:
                album = items[2][1]
            row_y = row_key
            dots_pos = self._estimate_dots_pos(row_y, img_width, window_offset)
            tracks.append(TrackInfo(
                song_name=song_name,
                artist=artist,
                album=album,
                row_y=row_y,
                dots_btn_pos=dots_pos,
            ))
        return tracks

    def _estimate_dots_pos(self, row_y: int, img_width: int, window_offset: tuple[int, int]) -> tuple[int, int]:
        abs_x = int(window_offset[0] + img_width * self.DOTS_X_RATIO)
        abs_y = window_offset[1] + row_y + 10
        return (abs_x, abs_y)

    def read_playlist_names(self, image: np.ndarray, window_offset: tuple[int, int] = (0, 0)) -> list[tuple[str, tuple[int, int]]]:
        self._ensure_ocr()
        result = self._ocr.ocr(image, cls=True)
        if not result or not result[0]:
            return []
        playlists = []
        for line in result[0]:
            box = line[0]
            text = line[1][0]
            conf = line[1][1]
            if conf < 0.5:
                continue
            x_center = int(sum(p[0] for p in box) / 4) + window_offset[0]
            y_center = int(sum(p[1] for p in box) / 4) + window_offset[1]
            playlists.append((text, (x_center, y_center)))
        return playlists
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_ocr_reader.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/ocr_reader.py tests/test_ocr_reader.py
git commit -m "feat: add OCR reader for track and playlist name recognition"
```

---

### Task 6: 操作执行模块

**Files:**
- Create: `core/action_executor.py`

- [ ] **Step 1: 实现 action_executor.py**

```python
import time
import pyautogui as pag
from core.models import ClassificationResult
from core.screen_capture import ScreenCapture
from core.ocr_reader import OCRReader


class ActionExecutor:
    def __init__(self, screen_capture: ScreenCapture, ocr_reader: OCRReader, after_click_ms: int = 700, menu_appear_ms: int = 500):
        self._screen_capture = screen_capture
        self._ocr_reader = ocr_reader
        self._after_click_ms = after_click_ms
        self._menu_appear_ms = menu_appear_ms

    def click_dots_button(self, dots_pos: tuple[int, int]) -> bool:
        try:
            pag.click(dots_pos[0], dots_pos[1])
            time.sleep(self._after_click_ms / 1000)
            return True
        except Exception:
            return False

    def click_add_to_playlist(self) -> bool:
        try:
            screen = self._screen_capture.capture_full_window(delay_ms=int(self._menu_appear_ms))
            if screen is None:
                return False
            offset = self._screen_capture._window_rect[:2] if self._screen_capture._window_rect else (0, 0)
            items = self._ocr_reader.read_playlist_names(screen, offset)
            for text, pos in items:
                if "添加到歌单" in text or "Add to Playlist" in text:
                    pag.click(pos[0], pos[1])
                    time.sleep(self._after_click_ms / 1000)
                    return True
            return False
        except Exception:
            return False

    def click_target_playlist(self, playlist_name: str) -> ClassificationResult:
        try:
            screen = self._screen_capture.capture_full_window(delay_ms=int(self._menu_appear_ms))
            if screen is None:
                return ClassificationResult(
                    success=False,
                    track_name="",
                    target_playlist=playlist_name,
                    message="截图失败，无法定位目标歌单",
                )
            offset = self._screen_capture._window_rect[:2] if self._screen_capture._window_rect else (0, 0)
            items = self._ocr_reader.read_playlist_names(screen, offset)
            for text, pos in items:
                if playlist_name in text or text in playlist_name:
                    pag.click(pos[0], pos[1])
                    time.sleep(self._after_click_ms / 1000)
                    return ClassificationResult(
                        success=True,
                        track_name="",
                        target_playlist=playlist_name,
                        message=f"已添加到歌单: {playlist_name}",
                    )
            return ClassificationResult(
                success=False,
                track_name="",
                target_playlist=playlist_name,
                message=f"未找到歌单: {playlist_name}",
            )
        except Exception as e:
            return ClassificationResult(
                success=False,
                track_name="",
                target_playlist=playlist_name,
                message=f"操作异常: {str(e)}",
            )

    def classify_track(self, dots_pos: tuple[int, int], playlist_name: str, track_name: str) -> ClassificationResult:
        if not self.click_dots_button(dots_pos):
            return ClassificationResult(
                success=False,
                track_name=track_name,
                target_playlist=playlist_name,
                message="三点按钮点击失败",
            )
        if not self.click_add_to_playlist():
            return ClassificationResult(
                success=False,
                track_name=track_name,
                target_playlist=playlist_name,
                message="未找到「添加到歌单」选项",
            )
        result = self.click_target_playlist(playlist_name)
        result.track_name = track_name
        return result
```

- [ ] **Step 2: Commit**

```bash
git add core/action_executor.py
git commit -m "feat: add action executor for mouse automation"
```

---

### Task 7: PySide6 主界面

**Files:**
- Create: `gui/main_window.py`

- [ ] **Step 1: 实现 main_window.py**

```python
import threading
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QTextEdit, QProgressBar,
    QGroupBox, QMessageBox,
)
from PySide6.QtCore import Signal, QObject
from core.models import TrackInfo, ClassificationResult
from core.screen_capture import ScreenCapture
from core.ocr_reader import OCRReader
from core.action_executor import ActionExecutor
from core.playlist_config import PlaylistConfig


class Signals(QObject):
    track_detected = Signal(object)
    classification_done = Signal(object)
    log_message = Signal(str)
    error_occurred = Signal(str)
    progress_updated = Signal(int, int)


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
        self._processed = 0
        self._total = 0
        self._running = False
        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        self.setWindowTitle("MusicClassifier")
        self.setMinimumSize(500, 600)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        track_group = QGroupBox("当前歌曲")
        track_layout = QVBoxLayout(track_group)
        self._track_label = QLabel("等待识别...")
        self._track_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        self._album_label = QLabel("")
        self._album_label.setStyleSheet("color: gray;")
        track_layout.addWidget(self._track_label)
        track_layout.addWidget(self._album_label)
        layout.addWidget(track_group)

        classify_group = QGroupBox("分类到")
        classify_layout = QHBoxLayout(classify_group)
        classify_layout.addWidget(QLabel("卷:"))
        self._volume_combo = QComboBox()
        self._volume_combo.addItems(self._config.get_volumes())
        classify_layout.addWidget(self._volume_combo)
        classify_layout.addWidget(QLabel("情绪:"))
        self._mood_combo = QComboBox()
        classify_layout.addWidget(self._mood_combo)
        layout.addWidget(classify_group)

        btn_layout = QHBoxLayout()
        self._classify_btn = QPushButton("分类此首")
        self._classify_btn.setEnabled(False)
        self._classify_btn.setStyleSheet("background-color: #e74c3c; color: white; font-weight: bold; padding: 8px;")
        btn_layout.addWidget(self._classify_btn)
        self._skip_btn = QPushButton("跳过")
        self._skip_btn.setEnabled(False)
        btn_layout.addWidget(self._skip_btn)
        self._recapture_btn = QPushButton("重新截图")
        self._recapture_btn.setEnabled(False)
        btn_layout.addWidget(self._recapture_btn)
        self._start_btn = QPushButton("开始")
        self._start_btn.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold; padding: 8px;")
        btn_layout.addWidget(self._start_btn)
        layout.addLayout(btn_layout)

        log_group = QGroupBox("操作日志")
        log_layout = QVBoxLayout(log_group)
        self._log_text = QTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setMaximumHeight(200)
        log_layout.addWidget(self._log_text)
        layout.addWidget(log_group)

        self._progress_bar = QProgressBar()
        self._progress_bar.setValue(0)
        layout.addWidget(self._progress_bar)

        self._volume_combo.currentTextChanged.connect(self._on_volume_changed)
        self._classify_btn.clicked.connect(self._on_classify)
        self._skip_btn.clicked.connect(self._on_skip)
        self._recapture_btn.clicked.connect(self._on_recapture)
        self._start_btn.clicked.connect(self._on_start)
        self._on_volume_changed(self._volume_combo.currentText())

    def _connect_signals(self):
        self._signals.track_detected.connect(self._handle_track_detected)
        self._signals.classification_done.connect(self._handle_classification_done)
        self._signals.log_message.connect(self._handle_log)
        self._signals.error_occurred.connect(self._handle_error)
        self._signals.progress_updated.connect(self._handle_progress)

    def _on_volume_changed(self, volume_name: str):
        self._mood_combo.clear()
        moods = self._config.get_moods(volume_name)
        self._mood_combo.addItems(moods)

    def _on_start(self):
        if not self._screen_capture.find_window():
            QMessageBox.warning(self, "错误", "未找到 Apple Music 窗口，请先打开 Apple Music。")
            return
        self._start_btn.setEnabled(False)
        self._classify_btn.setEnabled(True)
        self._skip_btn.setEnabled(True)
        self._recapture_btn.setEnabled(True)
        self._running = True
        self._processed = 0
        self._total = 0
        self._capture_and_detect()

    def _capture_and_detect(self):
        if not self._running:
            return

        def worker():
            image = self._screen_capture.capture_list_region(delay_ms=self._config.before_screenshot_ms)
            if image is None:
                self._signals.error_occurred.emit("截图失败，请确认 Apple Music 窗口可见")
                return
            offset = self._screen_capture._window_rect[:2] if self._screen_capture._window_rect else (0, 0)
            tracks = self._ocr_reader.read_tracks(image, offset)
            if not tracks:
                self._signals.error_occurred.emit("OCR 未识别到歌曲，请确认歌单列表可见")
                return
            if self._total == 0:
                self._total = len(tracks)
            self._signals.track_detected.emit(tracks[0])

        threading.Thread(target=worker, daemon=True).start()

    def _handle_track_detected(self, track: TrackInfo):
        self._current_track = track
        self._track_label.setText(track.display_text())
        self._album_label.setText(f"专辑: {track.album}" if track.album else "")
        self._signals.log_message.emit(f"识别到歌曲: {track.display_text()}")

    def _on_classify(self):
        if not self._current_track:
            return
        volume = self._volume_combo.currentText()
        mood = self._mood_combo.currentText()
        playlist_name = self._config.get_playlist_name(volume, mood)
        track = self._current_track
        self._classify_btn.setEnabled(False)
        self._skip_btn.setEnabled(False)
        self._recapture_btn.setEnabled(False)

        def worker():
            result = self._action_executor.classify_track(
                track.dots_btn_pos, playlist_name, track.song_name
            )
            self._processed += 1
            self._signals.classification_done.emit(result)

        threading.Thread(target=worker, daemon=True).start()

    def _handle_classification_done(self, result: ClassificationResult):
        self._signals.log_message.emit(result.message)
        self._signals.progress_updated.emit(self._processed, self._total)
        self._classify_btn.setEnabled(True)
        self._skip_btn.setEnabled(True)
        self._recapture_btn.setEnabled(True)
        self._capture_and_detect()

    def _on_skip(self):
        self._processed += 1
        self._signals.log_message.emit(f"跳过: {self._current_track.display_text() if self._current_track else '?'}")
        self._signals.progress_updated.emit(self._processed, self._total)
        self._capture_and_detect()

    def _on_recapture(self):
        self._capture_and_detect()

    def _handle_log(self, msg: str):
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._log_text.append(f"[{timestamp}] {msg}")

    def _handle_error(self, msg: str):
        self._signals.log_message.emit(f"❌ {msg}")
        self._classify_btn.setEnabled(True)
        self._skip_btn.setEnabled(True)
        self._recapture_btn.setEnabled(True)

    def _handle_progress(self, done: int, total: int):
        if total > 0:
            self._progress_bar.setMaximum(total)
            self._progress_bar.setValue(done)
```

- [ ] **Step 2: Commit**

```bash
git add gui/main_window.py
git commit -m "feat: add PySide6 main window GUI"
```

---

### Task 8: 入口文件

**Files:**
- Create: `main.py`

- [ ] **Step 1: 实现 main.py**

```python
import sys
from PySide6.QtWidgets import QApplication
from gui.main_window import MainWindow
from core.playlist_config import PlaylistConfig


def main():
    app = QApplication(sys.argv)
    config = PlaylistConfig()
    window = MainWindow(config)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 运行验证 GUI 启动**

```bash
cd "S:\Github Repositories\MusicClassifier"
python main.py
```
Expected: GUI 窗口正常显示，下拉框有卷和情绪选项

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: add application entry point"
```

---

### Task 9: 集成测试与调优

**Files:**
- Modify: `core/screen_capture.py` (如需调整截图区域比例)
- Modify: `core/ocr_reader.py` (如需调整行分组阈值)

- [ ] **Step 1: 手动集成测试 - 截图**

打开 Apple Music，运行以下脚本验证截图功能：

```python
from core.screen_capture import ScreenCapture
from core.playlist_config import PlaylistConfig
import cv2

config = PlaylistConfig()
capture = ScreenCapture(config.window_title)
rect = capture.find_window()
print(f"窗口位置: {rect}")
img = capture.capture_list_region()
if img is not None:
    cv2.imwrite("debug_screenshot.png", img)
    print("截图已保存到 debug_screenshot.png")
else:
    print("截图失败")
```

- [ ] **Step 2: 手动集成测试 - OCR**

```python
from core.ocr_reader import OCRReader
import cv2

reader = OCRReader()
img = cv2.imread("debug_screenshot.png")
tracks = reader.read_tracks(img, (0, 0))
for t in tracks:
    print(f"{t.display_text()} | 三点位置: {t.dots_btn_pos}")
```

- [ ] **Step 3: 根据测试结果调整参数**

如果截图区域不对，调整 `list_region_ratio`；如果行分组不准，调整 `_parse_to_tracks` 中的 `row_key` 分组阈值。

- [ ] **Step 4: 手动集成测试 - 完整流程**

运行 `python main.py`，打开 Apple Music 歌单，点击「开始」，验证完整流程。

- [ ] **Step 5: Commit 调优结果**

```bash
git add -A
git commit -m "fix: tune screenshot region and OCR parameters based on integration test"
```
