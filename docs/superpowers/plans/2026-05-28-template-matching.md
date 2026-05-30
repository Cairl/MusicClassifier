# 模板匹配与采集向导实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 OpenCV 模板匹配替代 OCR 处理菜单操作，实现完整 6 步归类流程（含两级菜单导航和归类后删除），并提供应用内模板采集向导。

**Architecture:** 新增 `TemplateLibrary` 模块管理模板图片的存储和 `cv2.matchTemplate` 匹配。重构 `ActionExecutor` 为 6 步流程，每步截图+模板匹配+点击。GUI 层新增 `CropDialog`（截图裁剪）和 `CaptureWizard`（引导采集），`MainWindow` 集成模板缺失检查和采集入口。

**Tech Stack:** Python 3.12, PySide6, OpenCV (`cv2.matchTemplate`, `TM_CCOEFF_NORMED`), pyautogui, numpy

---

## File Structure

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `core/models.py` | 新增 `MatchResult` 数据类 |
| Modify | `core/playlist_config.py` | 新增 `template_threshold` 和 `templates_dir` 属性 |
| Create | `core/template_library.py` | 模板存储、匹配、缺失检测 |
| Create | `tests/test_template_library.py` | TemplateLibrary 单元测试 |
| Modify | `core/action_executor.py` | 6 步流程，移除 OCR 依赖，接入 TemplateLibrary |
| Create | `tests/test_action_executor.py` | ActionExecutor 单元测试 |
| Create | `gui/crop_dialog.py` | 截图裁剪对话框 |
| Create | `gui/capture_wizard.py` | 模板采集向导对话框 |
| Modify | `gui/main_window.py` | 集成模板检查、volume_name 传递、菜单入口 |
| Modify | `config.json` | 新增 `template_matching` 字段 |
| Modify | `.gitignore` | 添加 `templates/` |

---

### Task 1: MatchResult 数据类

**Files:**
- Modify: `core/models.py:1-22`
- Modify: `tests/test_models.py:1-60`

- [ ] **Step 1: 编写 MatchResult 测试**

在 `tests/test_models.py` 末尾添加:

```python
class TestMatchResult:
    def test_create_match_result(self):
        from core.models import MatchResult
        result = MatchResult(position=(150, 300), confidence=0.92)
        assert result.position == (150, 300)
        assert result.confidence == 0.92
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_models.py::TestMatchResult -v`
Expected: FAIL — `ImportError: cannot import name 'MatchResult'`

- [ ] **Step 3: 在 models.py 中添加 MatchResult**

在 `core/models.py` 的 `ClassificationResult` 之后添加:

```python
@dataclass
class MatchResult:
    position: tuple[int, int]
    confidence: float
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_models.py -v`
Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add core/models.py tests/test_models.py
git commit -m "feat: add MatchResult dataclass to models"
```

---

### Task 2: PlaylistConfig 模板匹配配置

**Files:**
- Modify: `core/playlist_config.py:70-85`
- Modify: `tests/test_playlist_config.py:63-80`

- [ ] **Step 1: 编写配置属性测试**

在 `tests/test_playlist_config.py` 末尾添加:

```python
    def test_template_threshold_default(self):
        config = PlaylistConfig()
        assert config.template_threshold == 0.8

    def test_templates_dir_default(self):
        config = PlaylistConfig()
        assert config.templates_dir == "templates"

    def test_template_matching_from_config(self):
        data = {
            "volumes": [],
            "template_matching": {
                "threshold": 0.75,
                "templates_dir": "custom_templates"
            }
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
            path = f.name
        config = PlaylistConfig(path)
        assert config.template_threshold == 0.75
        assert config.templates_dir == "custom_templates"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_playlist_config.py -v -k "template"`
Expected: FAIL — `AttributeError: 'PlaylistConfig' object has no attribute 'template_threshold'`

- [ ] **Step 3: 在 PlaylistConfig 中添加属性**

在 `core/playlist_config.py` 的 `window_title` 属性之后添加:

```python
    @property
    def template_threshold(self) -> float:
        return self._data.get("template_matching", {}).get("threshold", 0.8)

    @property
    def templates_dir(self) -> str:
        return self._data.get("template_matching", {}).get("templates_dir", "templates")
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_playlist_config.py -v`
Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add core/playlist_config.py tests/test_playlist_config.py
git commit -m "feat: add template_matching config properties to PlaylistConfig"
```

---

### Task 3: TemplateLibrary 模块

**Files:**
- Create: `core/template_library.py`
- Create: `tests/test_template_library.py`

- [ ] **Step 1: 编写 TemplateLibrary 测试**

创建 `tests/test_template_library.py`:

```python
import numpy as np
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from core.template_library import TemplateLibrary
from core.models import MatchResult


class TestTemplateLibrary:
    def test_init(self, tmp_path):
        lib = TemplateLibrary(tmp_path)
        assert lib._threshold == 0.8

    def test_init_custom_threshold(self, tmp_path):
        lib = TemplateLibrary(tmp_path, threshold=0.7)
        assert lib._threshold == 0.7

    def test_has_template_true(self, tmp_path):
        vol_dir = tmp_path / "volumes"
        vol_dir.mkdir()
        (vol_dir / "风之卷.png").write_bytes(b"\x89PNG")
        lib = TemplateLibrary(tmp_path)
        assert lib.has_template("volumes/风之卷") is True

    def test_has_template_false(self, tmp_path):
        lib = TemplateLibrary(tmp_path)
        assert lib.has_template("volumes/不存在") is False

    def test_save_template(self, tmp_path):
        lib = TemplateLibrary(tmp_path)
        img = np.zeros((50, 200, 3), dtype=np.uint8)
        with patch("core.template_library.cv2") as mock_cv2:
            mock_cv2.imwrite.return_value = True
            lib.save_template("playlists/季风", img)
        assert (tmp_path / "playlists").exists()
        mock_cv2.imwrite.assert_called_once()

    def test_delete_template(self, tmp_path):
        vol_dir = tmp_path / "volumes"
        vol_dir.mkdir()
        f = vol_dir / "风之卷.png"
        f.write_bytes(b"\x89PNG")
        lib = TemplateLibrary(tmp_path)
        lib.delete_template("volumes/风之卷")
        assert not f.exists()

    def test_list_templates(self, tmp_path):
        (tmp_path / "ui").mkdir()
        (tmp_path / "ui" / "add_to_playlist.png").write_bytes(b"\x89PNG")
        (tmp_path / "volumes").mkdir()
        (tmp_path / "volumes" / "风之卷.png").write_bytes(b"\x89PNG")
        (tmp_path / "volumes" / "花之卷.png").write_bytes(b"\x89PNG")
        lib = TemplateLibrary(tmp_path)
        result = lib.list_templates()
        assert "ui" in result
        assert "add_to_playlist" in result["ui"]
        assert "volumes" in result
        assert len(result["volumes"]) == 2

    def test_list_templates_empty(self, tmp_path):
        lib = TemplateLibrary(tmp_path)
        result = lib.list_templates()
        assert result == {}

    @patch("core.template_library.cv2")
    def test_find_template_success(self, mock_cv2, tmp_path):
        vol_dir = tmp_path / "volumes"
        vol_dir.mkdir()
        (vol_dir / "风之卷.png").write_bytes(b"\x89PNG")
        mock_cv2.imread.return_value = np.zeros((30, 100, 3), dtype=np.uint8)
        mock_cv2.matchTemplate.return_value = np.array([[0.95]])
        mock_cv2.TM_CCOEFF_NORMED = 5
        mock_cv2.minMaxLoc.return_value = (0.0, 0.95, (0, 0), (10, 20))
        screenshot = np.zeros((400, 600, 3), dtype=np.uint8)
        lib = TemplateLibrary(tmp_path, threshold=0.8)
        result = lib.find_template(screenshot, "volumes/风之卷")
        assert result is not None
        assert isinstance(result, MatchResult)
        assert result.confidence == 0.95
        assert result.position == (60, 35)

    @patch("core.template_library.cv2")
    def test_find_template_below_threshold(self, mock_cv2, tmp_path):
        vol_dir = tmp_path / "volumes"
        vol_dir.mkdir()
        (vol_dir / "风之卷.png").write_bytes(b"\x89PNG")
        mock_cv2.imread.return_value = np.zeros((30, 100, 3), dtype=np.uint8)
        mock_cv2.matchTemplate.return_value = np.array([[0.5]])
        mock_cv2.TM_CCOEFF_NORMED = 5
        mock_cv2.minMaxLoc.return_value = (0.0, 0.5, (0, 0), (10, 20))
        screenshot = np.zeros((400, 600, 3), dtype=np.uint8)
        lib = TemplateLibrary(tmp_path, threshold=0.8)
        result = lib.find_template(screenshot, "volumes/风之卷")
        assert result is None

    def test_find_template_no_template_file(self, tmp_path):
        screenshot = np.zeros((400, 600, 3), dtype=np.uint8)
        lib = TemplateLibrary(tmp_path)
        result = lib.find_template(screenshot, "volumes/不存在")
        assert result is None

    def test_get_missing_templates(self, tmp_path):
        (tmp_path / "ui").mkdir()
        (tmp_path / "ui" / "add_to_playlist.png").write_bytes(b"\x89PNG")
        (tmp_path / "volumes").mkdir()
        (tmp_path / "volumes" / "风之卷.png").write_bytes(b"\x89PNG")
        (tmp_path / "playlists").mkdir()
        (tmp_path / "playlists" / "季风.png").write_bytes(b"\x89PNG")
        lib = TemplateLibrary(tmp_path)
        mock_config = MagicMock()
        mock_config.get_volumes.return_value = ["风之卷", "花之卷"]
        mock_config.get_all_moods_flat.return_value = [
            {"volume": "风之卷", "mood_name": "季风", "tag": "VIGOROUS", "playlist": "季风"},
            {"volume": "风之卷", "mood_name": "飓风", "tag": "TENSE", "playlist": "飓风"},
            {"volume": "花之卷", "mood_name": "春化", "tag": "VIGOROUS", "playlist": "春化"},
        ]
        missing = lib.get_missing_templates(mock_config)
        assert "ui/add_to_playlist" not in missing
        assert "volumes/风之卷" not in missing
        assert "volumes/花之卷" in missing
        assert "playlists/季风" not in missing
        assert "playlists/飓风" in missing
        assert "playlists/春化" in missing
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_template_library.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.template_library'`

- [ ] **Step 3: 实现 TemplateLibrary**

创建 `core/template_library.py`:

```python
import cv2
import numpy as np
from pathlib import Path
from dataclasses import dataclass
from core.models import MatchResult
from core.playlist_config import PlaylistConfig


class TemplateLibrary:
    def __init__(self, templates_dir: Path, threshold: float = 0.8):
        self._templates_dir = Path(templates_dir)
        self._threshold = threshold

    def _template_path(self, name: str) -> Path:
        return self._templates_dir / f"{name}.png"

    def find_template(self, screenshot: np.ndarray, name: str) -> MatchResult | None:
        path = self._template_path(name)
        if not path.exists():
            return None
        template = cv2.imread(str(path))
        if template is None:
            return None
        result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        if max_val < self._threshold:
            return None
        th, tw = template.shape[:2]
        center_x = max_loc[0] + tw // 2
        center_y = max_loc[1] + th // 2
        return MatchResult(position=(center_x, center_y), confidence=max_val)

    def has_template(self, name: str) -> bool:
        return self._template_path(name).exists()

    def save_template(self, name: str, image: np.ndarray) -> None:
        path = self._template_path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(path), image)

    def list_templates(self) -> dict[str, list[str]]:
        if not self._templates_dir.exists():
            return {}
        result: dict[str, list[str]] = {}
        for category_dir in sorted(self._templates_dir.iterdir()):
            if category_dir.is_dir():
                names = [p.stem for p in sorted(category_dir.glob("*.png"))]
                if names:
                    result[category_dir.name] = names
        return result

    def get_missing_templates(self, config: PlaylistConfig) -> list[str]:
        required = ["ui/add_to_playlist"]
        for vol_name in config.get_volumes():
            required.append(f"volumes/{vol_name}")
        for mood in config.get_all_moods_flat():
            required.append(f"playlists/{mood['playlist']}")
        return [name for name in required if not self.has_template(name)]

    def delete_template(self, name: str) -> None:
        path = self._template_path(name)
        if path.exists():
            path.unlink()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_template_library.py -v`
Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add core/template_library.py tests/test_template_library.py
git commit -m "feat: add TemplateLibrary with template matching and storage"
```

---

### Task 4: 重构 ActionExecutor — 6 步归类流程

**Files:**
- Modify: `core/action_executor.py:1-93`
- Create: `tests/test_action_executor.py`

- [ ] **Step 1: 编写 ActionExecutor 测试**

创建 `tests/test_action_executor.py`:

```python
import pytest
from unittest.mock import MagicMock, patch, call
from core.action_executor import ActionExecutor
from core.models import ClassificationResult, MatchResult


def make_executor(tmp_path):
    sc = MagicMock()
    sc._window_rect = (100, 50, 1300, 900)
    sc.capture_full_window.return_value = MagicMock()
    tl = MagicMock()
    return ActionExecutor(sc, tl, after_click_ms=10, menu_appear_ms=10), sc, tl


class TestClassifyTrack:
    @patch("core.action_executor.pyautogui")
    def test_full_flow_via_volume(self, mock_pag, tmp_path):
        executor, sc, tl = make_executor(tmp_path)
        tl.has_template.return_value = True
        tl.find_template.side_effect = [
            MatchResult(position=(200, 300), confidence=0.9),
            None,
            MatchResult(position=(150, 250), confidence=0.85),
            MatchResult(position=(180, 400), confidence=0.92),
        ]
        result = executor.classify_track((500, 200), "季风", "风之卷", "Beta")
        assert result.success is True
        assert result.track_name == "Beta"
        assert result.target_playlist == "季风"
        click_calls = [c for c in mock_pag.click.call_args_list]
        assert len(click_calls) == 5
        mock_pag.press.assert_called_once_with("delete")

    @patch("core.action_executor.pyautogui")
    def test_playlist_in_first_level(self, mock_pag, tmp_path):
        executor, sc, tl = make_executor(tmp_path)
        tl.has_template.return_value = True
        tl.find_template.side_effect = [
            MatchResult(position=(200, 300), confidence=0.9),
            MatchResult(position=(180, 400), confidence=0.88),
        ]
        result = executor.classify_track((500, 200), "季风", "风之卷", "Beta")
        assert result.success is True
        click_calls = [c for c in mock_pag.click.call_args_list]
        assert len(click_calls) == 4
        mock_pag.press.assert_called_once_with("delete")

    @patch("core.action_executor.pyautogui")
    def test_add_to_playlist_not_found(self, mock_pag, tmp_path):
        executor, sc, tl = make_executor(tmp_path)
        tl.has_template.return_value = True
        tl.find_template.return_value = None
        result = executor.classify_track((500, 200), "季风", "风之卷", "Beta")
        assert result.success is False
        assert "添加到播放列表" in result.message

    @patch("core.action_executor.pyautogui")
    def test_add_to_playlist_template_missing(self, mock_pag, tmp_path):
        executor, sc, tl = make_executor(tmp_path)
        tl.has_template.return_value = False
        result = executor.classify_track((500, 200), "季风", "风之卷", "Beta")
        assert result.success is False
        assert "不存在" in result.message

    @patch("core.action_executor.pyautogui")
    def test_volume_not_found(self, mock_pag, tmp_path):
        executor, sc, tl = make_executor(tmp_path)
        tl.has_template.return_value = True
        tl.find_template.side_effect = [
            MatchResult(position=(200, 300), confidence=0.9),
            None,
            None,
        ]
        result = executor.classify_track((500, 200), "季风", "风之卷", "Beta")
        assert result.success is False
        assert "风之卷" in result.message or "季风" in result.message

    @patch("core.action_executor.pyautogui")
    def test_dots_button_click_fails(self, mock_pag, tmp_path):
        executor, sc, tl = make_executor(tmp_path)
        mock_pag.click.side_effect = Exception("click failed")
        result = executor.classify_track((500, 200), "季风", "风之卷", "Beta")
        assert result.success is False
        assert "三点按钮" in result.message

    @patch("core.action_executor.pyautogui")
    def test_volume_template_missing(self, mock_pag, tmp_path):
        executor, sc, tl = make_executor(tmp_path)

        def has_template_side_effect(name):
            if name == "ui/add_to_playlist":
                return True
            if name == "playlists/季风":
                return False
            if name == "volumes/风之卷":
                return False
            return True

        tl.has_template.side_effect = has_template_side_effect
        tl.find_template.return_value = MatchResult(position=(200, 300), confidence=0.9)
        result = executor.classify_track((500, 200), "季风", "风之卷", "Beta")
        assert result.success is False
        assert "不存在" in result.message
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_action_executor.py -v`
Expected: FAIL — 新签名 `classify_track(dots_pos, playlist_name, volume_name, track_name)` 不匹配旧实现

- [ ] **Step 3: 重写 ActionExecutor**

用以下内容替换 `core/action_executor.py` 的全部内容:

```python
import time
import pyautogui
from core.models import ClassificationResult, MatchResult
from core.screen_capture import ScreenCapture
from core.template_library import TemplateLibrary


class ActionExecutor:
    def __init__(self, screen_capture: ScreenCapture, template_library: TemplateLibrary, after_click_ms: int = 700, menu_appear_ms: int = 500):
        self._screen_capture = screen_capture
        self._template_lib = template_library
        self._after_click_ms = after_click_ms
        self._menu_appear_ms = menu_appear_ms

    def click_dots_button(self, dots_pos: tuple[int, int]) -> bool:
        try:
            pyautogui.click(dots_pos[0], dots_pos[1])
            time.sleep(self._after_click_ms / 1000)
            return True
        except Exception:
            return False

    def _screenshot_and_find(self, template_name: str) -> tuple[int, int] | None:
        screen = self._screen_capture.capture_full_window(delay_ms=int(self._menu_appear_ms))
        if screen is None:
            return None
        match = self._template_lib.find_template(screen, template_name)
        if match is None:
            return None
        offset = self._screen_capture._window_rect[:2] if self._screen_capture._window_rect else (0, 0)
        return (match.position[0] + offset[0], match.position[1] + offset[1])

    def _click_template(self, template_name: str) -> bool:
        pos = self._screenshot_and_find(template_name)
        if pos is None:
            return False
        pyautogui.click(pos[0], pos[1])
        time.sleep(self._after_click_ms / 1000)
        return True

    def classify_track(self, dots_pos: tuple[int, int], playlist_name: str, volume_name: str, track_name: str) -> ClassificationResult:
        if not self.click_dots_button(dots_pos):
            return ClassificationResult(
                success=False,
                track_name=track_name,
                target_playlist=playlist_name,
                message="三点按钮点击失败",
            )

        if not self._template_lib.has_template("ui/add_to_playlist"):
            return ClassificationResult(
                success=False,
                track_name=track_name,
                target_playlist=playlist_name,
                message="模板 templates/ui/add_to_playlist.png 不存在，请先采集",
            )

        if not self._click_template("ui/add_to_playlist"):
            return ClassificationResult(
                success=False,
                track_name=track_name,
                target_playlist=playlist_name,
                message="未找到「添加到播放列表」按钮",
            )

        playlist_found_directly = False
        if self._template_lib.has_template(f"playlists/{playlist_name}"):
            if self._click_template(f"playlists/{playlist_name}"):
                playlist_found_directly = True

        if not playlist_found_directly:
            if not self._template_lib.has_template(f"volumes/{volume_name}"):
                return ClassificationResult(
                    success=False,
                    track_name=track_name,
                    target_playlist=playlist_name,
                    message=f"模板 templates/volumes/{volume_name}.png 不存在，请先采集",
                )

            if not self._click_template(f"volumes/{volume_name}"):
                return ClassificationResult(
                    success=False,
                    track_name=track_name,
                    target_playlist=playlist_name,
                    message=f"未找到歌单「{playlist_name}」或卷「{volume_name}」",
                )

            if not self._template_lib.has_template(f"playlists/{playlist_name}"):
                return ClassificationResult(
                    success=False,
                    track_name=track_name,
                    target_playlist=playlist_name,
                    message=f"模板 templates/playlists/{playlist_name}.png 不存在，请先采集",
                )

            if not self._click_template(f"playlists/{playlist_name}"):
                return ClassificationResult(
                    success=False,
                    track_name=track_name,
                    target_playlist=playlist_name,
                    message=f"未找到歌单「{playlist_name}」或卷「{volume_name}」",
                )

        if not self.click_dots_button(dots_pos):
            return ClassificationResult(
                success=False,
                track_name=track_name,
                target_playlist=playlist_name,
                message="三点按钮点击失败（删除前）",
            )

        try:
            pyautogui.press("delete")
            time.sleep(self._after_click_ms / 1000)
        except Exception:
            return ClassificationResult(
                success=False,
                track_name=track_name,
                target_playlist=playlist_name,
                message="删除操作失败",
            )

        return ClassificationResult(
            success=True,
            track_name=track_name,
            target_playlist=playlist_name,
            message=f"已添加到歌单: {playlist_name}",
        )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_action_executor.py -v`
Expected: 全部 PASS

- [ ] **Step 5: 运行全部测试确认无回归**

Run: `python -m pytest tests/ -v`
Expected: 全部 PASS（现有的 test_ocr_reader, test_screen_capture, test_models, test_playlist_config 不受影响）

- [ ] **Step 6: 提交**

```bash
git add core/action_executor.py tests/test_action_executor.py
git commit -m "feat: refactor ActionExecutor to 6-step flow with template matching"
```

---

### Task 5: CropDialog 截图裁剪对话框

**Files:**
- Create: `gui/crop_dialog.py`

- [ ] **Step 1: 实现 CropDialog**

创建 `gui/crop_dialog.py`:

```python
import numpy as np
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
from PySide6.QtCore import Qt, QPoint, QRect, Signal
from PySide6.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QMouseEvent


class CropDialog(QDialog):
    def __init__(self, screenshot: np.ndarray, parent=None):
        super().__init__(parent)
        self.setWindowTitle("框选模板区域")
        self.setMinimumSize(600, 400)
        self._original = screenshot
        self._crop_result: np.ndarray | None = None
        self._selecting = False
        self._start_point: QPoint | None = None
        self._end_point: QPoint | None = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignCenter)
        self._image_label.setMouseTracking(True)
        self._image_label.mousePressEvent = self._on_mouse_press
        self._image_label.mouseMoveEvent = self._on_mouse_move
        self._image_label.mouseReleaseEvent = self._on_mouse_release
        layout.addWidget(self._image_label)

        btn_layout = QHBoxLayout()
        confirm_btn = QPushButton("确认")
        confirm_btn.clicked.connect(self._on_confirm)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(confirm_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self._update_pixmap()

    def _numpy_to_qpixmap(self, img: np.ndarray) -> QPixmap:
        h, w = img.shape[:2]
        if len(img.shape) == 3 and img.shape[2] == 3:
            import cv2
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            qimg = QImage(rgb.data, w, h, w * 3, QImage.Format_RGB888)
        else:
            qimg = QImage(img.data, w, h, w, QImage.Format_Grayscale8)
        return QPixmap.fromImage(qimg.copy())

    def _update_pixmap(self):
        self._pixmap = self._numpy_to_qpixmap(self._original)
        label_size = self._image_label.size()
        if label_size.width() < 10 or label_size.height() < 10:
            label_size = self._image_label.parent().size()
        self._scaled = self._pixmap.scaled(label_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._scale_x = self._original.shape[1] / max(self._scaled.width(), 1)
        self._scale_y = self._original.shape[0] / max(self._scaled.height(), 1)
        self._render_image()

    def _render_image(self):
        display = self._scaled.copy()
        if self._start_point and self._end_point:
            painter = QPainter(display)
            overlay = QColor(0, 0, 0, 100)
            painter.fillRect(display.rect(), overlay)
            rect = QRect(self._start_point, self._end_point).normalized()
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillRect(rect, Qt.transparent)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            painter.setPen(QPen(QColor(233, 69, 96), 2))
            painter.drawRect(rect)
            painter.end()
        self._image_label.setPixmap(display)

    def _on_mouse_press(self, event: QMouseEvent):
        self._selecting = True
        self._start_point = event.pos()
        self._end_point = event.pos()

    def _on_mouse_move(self, event: QMouseEvent):
        if self._selecting:
            self._end_point = event.pos()
            self._render_image()

    def _on_mouse_release(self, event: QMouseEvent):
        self._selecting = False
        self._end_point = event.pos()
        self._render_image()

    def _on_confirm(self):
        if not self._start_point or not self._end_point:
            self.reject()
            return
        rect = QRect(self._start_point, self._end_point).normalized()
        if rect.width() < 5 or rect.height() < 5:
            self.reject()
            return
        x1 = int(rect.x() * self._scale_x)
        y1 = int(rect.y() * self._scale_y)
        x2 = int((rect.x() + rect.width()) * self._scale_x)
        y2 = int((rect.y() + rect.height()) * self._scale_y)
        x1, x2 = max(0, x1), min(self._original.shape[1], x2)
        y1, y2 = max(0, y1), min(self._original.shape[0], y2)
        self._crop_result = self._original[y1:y2, x1:x2]
        self.accept()

    def get_crop_result(self) -> np.ndarray | None:
        return self._crop_result
```

- [ ] **Step 2: 提交**

```bash
git add gui/crop_dialog.py
git commit -m "feat: add CropDialog for screenshot region selection"
```

---

### Task 6: CaptureWizard 模板采集向导

**Files:**
- Create: `gui/capture_wizard.py`

- [ ] **Step 1: 实现 CaptureWizard**

创建 `gui/capture_wizard.py`:

```python
import numpy as np
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QMessageBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from core.screen_capture import ScreenCapture
from core.template_library import TemplateLibrary
from core.playlist_config import PlaylistConfig
from gui.crop_dialog import CropDialog
import cv2


class CaptureWizard(QDialog):
    def __init__(self, screen_capture: ScreenCapture, template_lib: TemplateLibrary, config: PlaylistConfig, parent=None):
        super().__init__(parent)
        self._screen_capture = screen_capture
        self._template_lib = template_lib
        self._config = config
        self._steps = self._build_steps()
        self._current_step = 0
        self._cropped_image: np.ndarray | None = None
        self.setWindowTitle("模板采集向导")
        self.setMinimumSize(550, 500)
        self._init_ui()
        self._update_display()

    def _build_steps(self) -> list[dict]:
        steps = [
            {
                "name": "ui/add_to_playlist",
                "label": "UI 按钮: \"添加到播放列表\"",
                "instruction": "请右键 Apple Music 中任意歌曲，展开上下文菜单",
            }
        ]
        for vol_name in self._config.get_volumes():
            steps.append({
                "name": f"volumes/{vol_name}",
                "label": f"卷名: \"{vol_name}\"",
                "instruction": f"请右键歌曲 → 添加到播放列表，确保「{vol_name}」可见",
            })
        moods = self._config.get_all_moods_flat()
        for mood in moods:
            steps.append({
                "name": f"playlists/{mood['playlist']}",
                "label": f"歌单名: \"{mood['playlist']}\"",
                "instruction": f"请展开「{mood['volume']}」子菜单，确保「{mood['playlist']}」可见",
            })
        return steps

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self._step_label = QLabel()
        self._step_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff;")
        layout.addWidget(self._step_label)

        self._name_label = QLabel()
        self._name_label.setStyleSheet("font-size: 13px; color: #e94560;")
        layout.addWidget(self._name_label)

        self._instruction_label = QLabel()
        self._instruction_label.setWordWrap(True)
        self._instruction_label.setStyleSheet("font-size: 12px; color: #aaaaaa;")
        layout.addWidget(self._instruction_label)

        self._preview_label = QLabel()
        self._preview_label.setMinimumSize(400, 150)
        self._preview_label.setAlignment(Qt.AlignCenter)
        self._preview_label.setStyleSheet("background-color: #16213e; border-radius: 5px;")
        layout.addWidget(self._preview_label)

        btn_layout = QHBoxLayout()
        self._skip_btn = QPushButton("跳过")
        self._skip_btn.clicked.connect(self._on_skip)
        self._capture_btn = QPushButton("截取选区")
        self._capture_btn.setStyleSheet("background-color: #e94560; color: white; font-weight: bold; padding: 8px 16px;")
        self._capture_btn.clicked.connect(self._on_capture)
        self._retake_btn = QPushButton("确认并重截")
        self._retake_btn.clicked.connect(self._on_capture)
        self._retake_btn.setVisible(False)
        btn_layout.addWidget(self._skip_btn)
        btn_layout.addWidget(self._capture_btn)
        btn_layout.addWidget(self._retake_btn)
        layout.addLayout(btn_layout)

        self._progress = QProgressBar()
        self._progress.setMaximum(len(self._steps))
        layout.addWidget(self._progress)

    def _update_display(self):
        if self._current_step >= len(self._steps):
            self.accept()
            return
        step = self._steps[self._current_step]
        total = len(self._steps)
        self._step_label.setText(f"模板采集向导 ({self._current_step + 1}/{total})")
        self._name_label.setText(f"当前需要采集: {step['label']}")
        self._instruction_label.setText(step["instruction"])
        self._progress.setValue(self._current_step)
        self._cropped_image = None
        self._preview_label.setText("尚未截取")
        self._preview_label.setPixmap(QPixmap())
        self._retake_btn.setVisible(False)
        self._capture_btn.setText("截取选区")

    def _on_capture(self):
        self._screen_capture.activate_window()
        screenshot = self._screen_capture.capture_full_window(delay_ms=500)
        if screenshot is None:
            QMessageBox.warning(self, "错误", "截图失败，请确认 Apple Music 窗口可见")
            return
        crop_dialog = CropDialog(screenshot, self)
        if crop_dialog.exec() != QDialog.Accepted:
            return
        cropped = crop_dialog.get_crop_result()
        if cropped is None or cropped.size == 0:
            return
        self._cropped_image = cropped
        h, w = cropped.shape[:2]
        rgb = cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, w, h, w * 3, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg.copy())
        scaled = pixmap.scaled(self._preview_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._preview_label.setPixmap(scaled)
        self._retake_btn.setVisible(True)
        self._capture_btn.setText("确认并继续")
        self._capture_btn.clicked.disconnect()
        self._capture_btn.clicked.connect(self._on_confirm_and_next)

    def _on_confirm_and_next(self):
        if self._cropped_image is None:
            return
        step = self._steps[self._current_step]
        self._template_lib.save_template(step["name"], self._cropped_image)
        self._current_step += 1
        self._capture_btn.clicked.disconnect()
        self._capture_btn.clicked.connect(self._on_capture)
        self._update_display()

    def _on_skip(self):
        self._current_step += 1
        self._update_display()
```

- [ ] **Step 2: 提交**

```bash
git add gui/capture_wizard.py
git commit -m "feat: add CaptureWizard for guided template collection"
```

---

### Task 7: MainWindow 集成

**Files:**
- Modify: `gui/main_window.py:1-303`
- Modify: `config.json:1-46`
- Modify: `.gitignore:1-13`

- [ ] **Step 1: 更新 config.json**

在 `config.json` 的顶层对象中添加 `template_matching` 字段（在 `action_delays` 之前或之后）:

```json
  "template_matching": {
    "threshold": 0.8,
    "templates_dir": "templates"
  }
```

- [ ] **Step 2: 更新 .gitignore**

在 `.gitignore` 末尾添加:

```
templates/
```

- [ ] **Step 3: 修改 main_window.py — 添加导入**

在 `gui/main_window.py` 顶部导入区域添加:

```python
from pathlib import Path
from core.template_library import TemplateLibrary
from gui.capture_wizard import CaptureWizard
```

- [ ] **Step 4: 修改 main_window.py — 构造函数添加 TemplateLibrary**

在 `MainWindow.__init__` 中，`self._action_executor` 创建之前添加 TemplateLibrary 初始化:

```python
        templates_path = Path(config.templates_dir)
        self._template_lib = TemplateLibrary(templates_path, threshold=config.template_threshold)
```

修改 `ActionExecutor` 的创建，将 `self._ocr_reader` 替换为 `self._template_lib`:

```python
        self._action_executor = ActionExecutor(
            self._screen_capture,
            self._template_lib,
            after_click_ms=config.after_click_ms,
            menu_appear_ms=config.menu_appear_ms,
        )
```

- [ ] **Step 5: 修改 main_window.py — 添加模板缺失提示条**

在 `_init_ui` 方法中，在 `grid_widget` 创建之前添加:

```python
        missing = self._template_lib.get_missing_templates(self._config)
        self._missing_label = QLabel("")
        self._missing_label.setStyleSheet("color: #f39c12; font-size: 12px; padding: 4px;")
        if missing:
            self._missing_label.setText(f"缺少 {len(missing)} 个模板，请先进行模板采集")
        main_layout.addWidget(self._missing_label)
```

- [ ] **Step 6: 修改 main_window.py — 传递 volume_name**

修改按钮网格构建中 `btn.clicked.connect` 的 `partial` 调用，传递 `volume_name`:

将当前的:
```python
btn.clicked.connect(partial(self._on_classify, mood_info["playlist"]))
```

替换为:
```python
btn.clicked.connect(partial(self._on_classify, mood_info["playlist"], vol))
```

- [ ] **Step 7: 修改 main_window.py — 更新 _on_classify 签名**

将:
```python
    def _on_classify(self, playlist_name: str):
```

替换为:
```python
    def _on_classify(self, playlist_name: str, volume_name: str):
```

将 worker 中的 `classify_track` 调用更新:

```python
                result = self._action_executor.classify_track(
                    track.dots_btn_pos, playlist_name, volume_name, track.song_name
                )
```

- [ ] **Step 8: 修改 main_window.py — 添加模板采集菜单**

在 `_init_ui` 方法末尾添加:

```python
        from PySide6.QtGui import QAction
        menu_bar = self.menuBar()
        tools_menu = menu_bar.addMenu("工具")
        capture_action = QAction("模板采集", self)
        capture_action.triggered.connect(self._on_open_capture_wizard)
        tools_menu.addAction(capture_action)
```

在 `_on_recapture` 方法之后添加:

```python
    def _on_open_capture_wizard(self):
        if not self._screen_capture.find_window():
            QMessageBox.warning(self, "错误", "未找到 Apple Music 窗口，请先打开 Apple Music。")
            return
        wizard = CaptureWizard(
            self._screen_capture,
            self._template_lib,
            self._config,
            self,
        )
        wizard.exec()
        missing = self._template_lib.get_missing_templates(self._config)
        if missing:
            self._missing_label.setText(f"缺少 {len(missing)} 个模板，请先进行模板采集")
        else:
            self._missing_label.setText("")
```

- [ ] **Step 9: 修改 main_window.py — 禁用缺失模板对应的按钮**

在 `_handle_track_detected` 方法中，替换 `self._set_playlist_buttons_enabled(True)` 为更细粒度的控制:

将整个 `_handle_track_detected` 方法替换为:

```python
    def _handle_track_detected(self, track: TrackInfo):
        self._current_track = track
        self._track_label.setText(track.display_text())
        self._album_label.setText(f"专辑: {track.album}" if track.album else "")
        missing = self._template_lib.get_missing_templates(self._config)
        missing_playlists = {name.split("/", 1)[1] for name in missing if name.startswith("playlists/")}
        moods = self._config.get_all_moods_flat()
        for i, mood in enumerate(moods):
            if i < len(self._playlist_buttons):
                self._playlist_buttons[i].setEnabled(mood["playlist"] not in missing_playlists)
```

- [ ] **Step 10: 运行全部测试**

Run: `python -m pytest tests/ -v`
Expected: 全部 PASS

- [ ] **Step 11: 提交**

```bash
git add gui/main_window.py config.json .gitignore
git commit -m "feat: integrate TemplateLibrary and CaptureWizard into MainWindow"
```

---

### Task 8: 最终验证

- [ ] **Step 1: 运行全部测试**

Run: `python -m pytest tests/ -v`
Expected: 全部 PASS（18 + 新增测试）

- [ ] **Step 2: 启动应用确认无导入错误**

Run: `python -c "from gui.main_window import MainWindow; from core.template_library import TemplateLibrary; from gui.capture_wizard import CaptureWizard; from gui.crop_dialog import CropDialog; print('All imports OK')"`
Expected: `All imports OK`

- [ ] **Step 3: 确认模板目录结构**

Run: `python -c "from pathlib import Path; dirs = ['templates/ui', 'templates/volumes', 'templates/playlists']; [Path(d).mkdir(parents=True, exist_ok=True) for d in dirs]; print('Dirs created')"`
Expected: `Dirs created`

清理空目录（仅在不需要时）:

```bash
rmdir templates/ui templates/volumes templates/playlists 2>/dev/null; rmdir templates 2>/dev/null; echo "Cleanup done"
```
