# MusicClassifier UI 重构 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 MusicClassifier 的 PySide6 界面从功能型原型重构为 Apple 精雕风格的无边框窗口 + 侧边栏 + 网格布局。

**Architecture:** 新增 `SquircleButton`（连续曲率按钮）和 `SettingsPopover`（弹出菜单）两个 UI 组件。重写 `MainWindow` 为无边框侧边栏 + 5 列网格结构，移除跳过/重新截图/区域截图功能，简化工作流为三阶段状态机。`ScreenCapture` 移除自定义区域相关代码。

**Tech Stack:** Python 3.12, PySide6, QPainter/QPainterPath, QSS

---

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| `gui/squircle_button.py` | 新建 | Squircle 连续曲率 QPushButton |
| `gui/settings_popover.py` | 新建 | ⚙ 弹出菜单浮层 |
| `gui/main_window.py` | 重写 | 主窗口：侧边栏 + 网格 + 状态机 |
| `main.py` | 修改 | 无边框窗口初始化 |
| `core/screen_capture.py` | 修改 | 移除 `set_custom_region` |
| `tests/test_screen_capture.py` | 修改 | 更新测试 |

`core/action_executor.py` 和 `core/models.py` **不变** — 分类逻辑和数据结构无需改动。

---

### Task 1: 创建 SquircleButton 组件

**Files:**
- Create: `gui/squircle_button.py`

- [ ] **Step 1: 创建 SquircleButton 类**

```python
from PySide6.QtWidgets import QPushButton
from PySide6.QtCore import Qt, QSize, Property, QPropertyAnimation
from PySide6.QtGui import QPainter, QPainterPath, QColor, QBrush, QPen


class SquircleButton(QPushButton):
    def __init__(self, text="", parent=None, color="#007aff", icon_text=""):
        super().__init__(text, parent)
        self._color = QColor(color)
        self._icon_text = icon_text
        self._hovered = False
        self._pressed = False
        self._fill_color = QColor(color)
        self.setFixedSize(44, 44)
        self.setCursor(Qt.PointingHandCursor)
        self._animation = QPropertyAnimation(self, b"_fill_color")
        self._animation.setDuration(150)

    def setColor(self, color: str):
        self._color = QColor(color)
        self._fill_color = QColor(color)
        self.update()

    def setIconText(self, text: str):
        self._icon_text = text
        self.update()

    def _get_fill_color(self):
        return self._fill_color

    def _set_fill_color(self, color):
        self._fill_color = color
        self.update()

    fill_color = Property(QColor, _get_fill_color, _set_fill_color)

    def sizeHint(self):
        return QSize(44, 44)

    def minimumSizeHint(self):
        return QSize(44, 44)

    def enterEvent(self, event):
        self._hovered = True
        self._animation.stop()
        if self._color == QColor("#ff3b30"):
            target = QColor("#ff453a")
        else:
            target = QColor("#0077ed")
        self._animation.setStartValue(self._fill_color)
        self._animation.setEndValue(target)
        self._animation.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._animation.stop()
        self._animation.setStartValue(self._fill_color)
        self._animation.setEndValue(self._color)
        self._animation.start()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self._pressed = True
        self._animation.stop()
        self._fill_color = QColor("#005bb5") if self._color != QColor("#ff3b30") else QColor("#cc3028")
        self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._pressed = False
        if self._hovered:
            if self._color == QColor("#ff3b30"):
                self._fill_color = QColor("#ff453a")
            else:
                self._fill_color = QColor("#0077ed")
        else:
            self._fill_color = self._color
        self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        path = QPainterPath()
        r = min(w, h) * 0.22
        path.moveTo(r, 0)
        path.lineTo(w - r, 0)
        path.cubicTo(w - r * 0.45, 0, w, r * 0.45, w, r)
        path.lineTo(w, h - r)
        path.cubicTo(w, h - r * 0.45, w - r * 0.45, h, w - r, h)
        path.lineTo(r, h)
        path.cubicTo(r * 0.45, h, 0, h - r * 0.45, 0, h - r)
        path.lineTo(0, r)
        path.cubicTo(0, r * 0.45, r * 0.45, 0, r, 0)
        path.closeSubpath()

        painter.fillPath(path, self._fill_color)

        if not self._icon_text:
            return

        painter.setPen(QPen(QColor("#ffffff")))
        font = painter.font()
        font.setPixelSize(18)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignCenter, self._icon_text)
```

- [ ] **Step 2: 验证模块可导入**

```bash
python -c "from gui.squircle_button import SquircleButton; print('OK')"
```

---

### Task 2: 创建 SettingsPopover 组件

**Files:**
- Create: `gui/settings_popover.py`

- [ ] **Step 1: 创建 SettingsPopover 类**

```python
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt, Signal, QPoint, QPropertyAnimation
from PySide6.QtGui import QPainter, QPainterPath, QColor, QBrush


class SettingsPopover(QWidget):
    template_capture_requested = Signal()
    about_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(160, 90)
        self._items = [
            ("模板采集", "template"),
            ("关于", "about"),
        ]
        self._build_ui()

    def _build_ui(self):
        container = QWidget(self)
        container.setObjectName("popover_container")
        container.setStyleSheet("""
            #popover_container {
                background: #ffffff;
                border-radius: 10px;
            }
        """)
        container.setGeometry(6, 6, 148, 78)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)

        for label, key in self._items:
            item = QLabel(label)
            item.setObjectName(f"popover_item_{key}")
            item.setFixedHeight(34)
            item.setCursor(Qt.PointingHandCursor)
            item.setAlignment(Qt.AlignVCenter)
            item.setStyleSheet(f"""
                #{item.objectName()} {{
                    padding: 0 12px;
                    font-size: 13px;
                    color: #1d1d1f;
                    border-radius: 8px;
                }}
                #{item.objectName()}:hover {{
                    background: #f2f2f7;
                }}
            """)
            item.mousePressEvent = lambda e, k=key: self._on_click(k)
            layout.addWidget(item)

    def _on_click(self, key: str):
        if key == "template":
            self.template_capture_requested.emit()
        elif key == "about":
            self.about_requested.emit()
        self.hide()

    def show_at(self, pos: QPoint):
        self.move(pos)
        self.show()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        r = 10
        wr = self.width()
        hr = self.height()
        path.addRoundedRect(0, 0, wr, hr, r, r)
        painter.fillPath(path, QBrush(QColor(0, 0, 0, 40)))
```

- [ ] **Step 2: 验证模块可导入**

```bash
python -c "from gui.settings_popover import SettingsPopover; print('OK')"
```

---

### Task 3: 重写 MainWindow 布局

**Files:**
- Modify: `gui/main_window.py`（完全重写）

- [ ] **Step 1: 重写 `gui/main_window.py` 的导入和 QSS**

```python
import sys
import traceback
import threading
from functools import partial
from pathlib import Path
import numpy as np
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QMessageBox, QApplication,
)
from PySide6.QtCore import Signal, QObject, Qt, QPoint
from PySide6.QtGui import QAction, QMouseEvent
from core.models import TrackInfo, ClassificationResult
from core.screen_capture import ScreenCapture
from core.ocr_reader import OCRReader
from core.action_executor import ActionExecutor
from core.playlist_config import PlaylistConfig
from core.template_library import TemplateLibrary
from gui.capture_wizard import CaptureWizard
from gui.squircle_button import SquircleButton
from gui.settings_popover import SettingsPopover


APPLE_LIGHT_QSS = """
QMainWindow {
    background: #f2f2f7;
}
QWidget#central {
    background: #f2f2f7;
}
QWidget#titlebar {
    background: #f2f2f7;
    border-bottom: 0.5px solid rgba(0, 0, 0, 0.06);
}
QLabel#window_title {
    font-size: 11px;
    font-weight: 600;
    color: #1d1d1f;
}
QWidget#sidebar {
    background: rgba(255, 255, 255, 0.5);
    border-right: 0.5px solid rgba(0, 0, 0, 0.06);
}
QWidget#track_card {
    background: #ffffff;
    border-radius: 14px;
}
QLabel#track_name {
    font-size: 17px;
    font-weight: 700;
    color: #1d1d1f;
}
QLabel#track_subtitle {
    font-size: 13px;
    color: #8e8e93;
}
QLabel#volume_tag {
    font-size: 12px;
    color: #8e8e93;
}
QLabel#tag_header {
    font-size: 10px;
    font-weight: 500;
    color: #8e8e93;
}
QLabel#volume_label {
    font-size: 13px;
    font-weight: 600;
    color: #1d1d1f;
}
QPushButton#playlist_btn {
    background: #ffffff;
    color: #aeaeb2;
    border: none;
    border-radius: 10px;
    padding: 10px 6px;
    font-size: 13px;
    font-weight: 500;
}
QPushButton#playlist_btn[active="true"] {
    color: #007aff;
    font-weight: 600;
}
QPushButton#playlist_btn:hover[active="true"] {
    background: #007aff;
    color: #ffffff;
}
QPushButton#playlist_btn:pressed[active="true"] {
    background: #005bb5;
    color: #ffffff;
}
QLabel#missing_warning {
    font-size: 12px;
    color: #ff9500;
    padding: 4px 8px;
}
QWidget#titlebar_btn_close {
    background: #ff5f57;
    border-radius: 5px;
}
QWidget#titlebar_btn_min {
    background: #febc2e;
    border-radius: 5px;
}
QWidget#titlebar_btn_max {
    background: #28c840;
    border-radius: 5px;
}
"""
```

- [ ] **Step 2: 重写 `MainWindow.__init__` 和 `_init_ui`**

```python
class Signals(QObject):
    track_detected = Signal(object)
    classification_done = Signal(object)
    error_occurred = Signal(str)


class MainWindow(QMainWindow):
    def __init__(self, config: PlaylistConfig):
        super().__init__(None, Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._config = config
        self._signals = Signals()
        self._screen_capture = ScreenCapture(config.window_title)
        self._ocr_reader = OCRReader()
        templates_path = Path(config.templates_dir)
        self._template_lib = TemplateLibrary(templates_path, threshold=config.template_threshold)
        self._action_executor = ActionExecutor(
            self._screen_capture,
            self._template_lib,
            after_click_ms=config.after_click_ms,
            menu_appear_ms=config.menu_appear_ms,
        )
        self._current_track: TrackInfo | None = None
        self._running = False
        self._playlist_buttons: list[QPushButton] = []
        self._settings_popover: SettingsPopover | None = None
        self._drag_pos: QPoint | None = None
        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        self.setWindowTitle("MusicClassifier")
        self.setMinimumSize(560, 500)
        self.setStyleSheet(APPLE_LIGHT_QSS)

        outer = QWidget()
        outer.setObjectName("outer")
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(8, 8, 8, 8)
        outer_layout.setSpacing(0)

        titlebar = QWidget()
        titlebar.setObjectName("titlebar")
        titlebar.setFixedHeight(32)
        titlebar_layout = QHBoxLayout(titlebar)
        titlebar_layout.setContentsMargins(12, 0, 12, 0)
        titlebar_layout.setSpacing(8)

        for obj_name, color in [("titlebar_btn_close", "#ff5f57"), ("titlebar_btn_min", "#febc2e"), ("titlebar_btn_max", "#28c840")]:
            dot = QWidget()
            dot.setObjectName(obj_name)
            dot.setFixedSize(10, 10)
            titlebar_layout.addWidget(dot)

        title_label = QLabel("MusicClassifier")
        title_label.setObjectName("window_title")
        title_label.setAlignment(Qt.AlignCenter)
        titlebar_layout.addWidget(title_label)
        titlebar_layout.addSpacing(42)

        outer_layout.addWidget(titlebar)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(60)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(8, 10, 8, 10)
        sidebar_layout.setSpacing(6)

        self._start_btn = SquircleButton(icon_text="▶")
        self._start_btn.clicked.connect(self._on_start_toggle)
        sidebar_layout.addWidget(self._start_btn)

        sidebar_layout.addStretch()

        self._settings_btn = SquircleButton(icon_text="⚙", color="#8e8e93")
        self._settings_btn.clicked.connect(self._on_settings)
        sidebar_layout.addWidget(self._settings_btn)

        body_layout.addWidget(sidebar)

        main_area = QWidget()
        main_layout = QVBoxLayout(main_area)
        main_layout.setContentsMargins(12, 10, 12, 10)
        main_layout.setSpacing(8)

        self._track_card = QWidget()
        self._track_card.setObjectName("track_card")
        track_card_layout = QVBoxLayout(self._track_card)
        track_card_layout.setContentsMargins(16, 14, 16, 14)
        track_card_layout.setSpacing(2)

        self._volume_tag = QLabel("")
        self._volume_tag.setObjectName("volume_tag")
        track_card_layout.addWidget(self._volume_tag)

        self._track_label = QLabel("点击 ▶ 开始识别")
        self._track_label.setObjectName("track_name")
        track_card_layout.addWidget(self._track_label)

        self._album_label = QLabel("")
        self._album_label.setObjectName("track_subtitle")
        track_card_layout.addWidget(self._album_label)

        main_layout.addWidget(self._track_card)

        self._missing_label = QLabel("")
        self._missing_label.setObjectName("missing_warning")
        self._missing_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self._missing_label)
        self._refresh_missing_label()

        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setSpacing(6)
        grid.setContentsMargins(0, 4, 0, 4)

        tags = ["活力", "紧张", "忧郁", "平静"]
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
            short_name = volume_name[0]
            vol_label = QLabel(short_name)
            vol_label.setObjectName("volume_label")
            vol_label.setAlignment(Qt.AlignCenter)
            grid.addWidget(vol_label, row_idx, 0)

            vol_moods = [m for m in moods if m["volume"] == volume_name]
            for col_idx, mood_info in enumerate(vol_moods, start=1):
                btn = QPushButton(mood_info["mood_name"])
                btn.setObjectName("playlist_btn")
                btn.setProperty("active", "false")
                btn.setEnabled(False)
                btn.clicked.connect(partial(self._on_classify, mood_info["playlist"], volume_name))
                self._playlist_buttons.append(btn)
                grid.addWidget(btn, row_idx, col_idx)

        main_layout.addWidget(grid_widget, stretch=1)
        body_layout.addWidget(main_area)
        outer_layout.addWidget(body)
        self.setCentralWidget(outer)
```

- [ ] **Step 3: 重写 `_connect_signals` 和 `_on_start_toggle`**

```python
    def _connect_signals(self):
        self._signals.track_detected.connect(self._handle_track_detected)
        self._signals.classification_done.connect(self._handle_classification_done)
        self._signals.error_occurred.connect(self._handle_error)

    def _on_start_toggle(self):
        if self._running:
            self._running = False
            self._start_btn.setColor("#007aff")
            self._start_btn.setIconText("▶")
            self._track_label.setText("已停止")
            self._album_label.setText("")
            self._volume_tag.setText("")
            self._set_playlist_buttons_active(False)
            return

        if not self._screen_capture.find_window():
            QMessageBox.warning(self, "错误", "未找到 Apple Music 窗口，请先打开 Apple Music。")
            return
        self._screen_capture.activate_window()
        self._running = True
        self._start_btn.setColor("#ff3b30")
        self._start_btn.setIconText("⏹")
        self._set_playlist_buttons_active(False)
        self._capture_and_detect()

    def _set_playlist_buttons_active(self, active: bool):
        for btn in self._playlist_buttons:
            btn.setProperty("active", "true" if active else "false")
            btn.setEnabled(active)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
```

- [ ] **Step 4: 重写 `_capture_and_detect` 和 handler**

```python
    def _capture_and_detect(self):
        if not self._running:
            return

        def worker():
            try:
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
            except Exception as e:
                traceback.print_exc()
                self._signals.error_occurred.emit(f"识别异常: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def _handle_track_detected(self, track: TrackInfo):
        self._current_track = track
        self._track_label.setText(track.display_text())
        self._album_label.setText(f"专辑: {track.album}" if track.album else "")
        self._volume_tag.setText("")
        self._set_playlist_buttons_active(True)
        missing = self._template_lib.get_missing_templates(self._config)
        missing_playlists = {name.split("/", 1)[1] for name in missing if name.startswith("playlists/")}
        moods = self._config.get_all_moods_flat()
        for i, mood in enumerate(moods):
            if i < len(self._playlist_buttons) and mood["playlist"] in missing_playlists:
                self._playlist_buttons[i].setEnabled(False)

    def _handle_error(self, msg: str):
        print(f"[ERROR] {msg}", file=sys.stderr, flush=True)
        self._track_label.setText(f"错误: {msg}")
        if self._running and self._current_track is not None:
            self._capture_and_detect()
```

- [ ] **Step 5: 重写 `_on_classify` 和 `_handle_classification_done`**

```python
    def _on_classify(self, playlist_name: str, volume_name: str):
        if not self._running or not self._current_track:
            return
        track = self._current_track
        volume_short = volume_name[0]
        self._volume_tag.setText(f"→ {volume_name}")
        self._set_playlist_buttons_active(False)

        def worker():
            try:
                result = self._action_executor.classify_track(
                    track.dots_btn_pos, playlist_name, volume_name, track.song_name
                )
                self._signals.classification_done.emit(result)
            except Exception as e:
                traceback.print_exc()
                self._signals.error_occurred.emit(f"分类失败: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def _handle_classification_done(self, result: ClassificationResult):
        if not self._running:
            return
        if result.success:
            self._capture_and_detect()
        else:
            self._signals.error_occurred.emit(result.message)
```

- [ ] **Step 6: 添加设置面板、窗口拖拽和 CaptureWizard 逻辑**

```python
    def _on_settings(self):
        if self._settings_popover is None:
            self._settings_popover = SettingsPopover()
            self._settings_popover.template_capture_requested.connect(self._on_open_capture_wizard)
            self._settings_popover.about_requested.connect(self._on_about)
        btn_pos = self._settings_btn.mapToGlobal(QPoint(0, self._settings_btn.height() + 4))
        self._settings_popover.show_at(btn_pos)

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
        self._refresh_missing_label()

    def _on_about(self):
        QMessageBox.about(self, "关于", "MusicClassifier\nApple Music 歌曲分类工具")

    def _refresh_missing_label(self):
        missing = self._template_lib.get_missing_templates(self._config)
        if missing:
            self._missing_label.setText(f"缺少 {len(missing)} 个模板，请先进行模板采集")
        else:
            self._missing_label.setText("")

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.LeftButton and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_pos = None
        event.accept()
```

- [ ] **Step 7: 验证模块可导入**

```bash
python -c "from gui.main_window import MainWindow; print('OK')"
```

---

### Task 4: 更新 main.py 支持无边框窗口

**Files:**
- Modify: `main.py`

- [ ] **Step 1: 修改 `main.py`**

搜索 `main.py` 中 `MainWindow(config)` 之后的 `window.show()`，不需要改动（frameless 已在 `MainWindow.__init__` 中通过 `Qt.FramelessWindowHint` 设置）。

确认 `main.py` 无需改动。验证：

```bash
python -c "
from main import main
print('main.py OK')
"
```

---

### Task 5: 清理 ScreenCapture 移除 set_custom_region

**Files:**
- Modify: `core/screen_capture.py`

- [ ] **Step 1: 移除 `_custom_region` 相关代码**

删除以下内容：
- `__init__` 中的 `self._custom_region: tuple | None = None`
- `set_custom_region` 方法（第 42-43 行）
- `capture_list_region` 中 `if self._custom_region:` 分支（第 46-50 行）

修改后的 `__init__`：

```python
def __init__(self, window_title: str, list_region_ratio: tuple | None = None):
    self._window_title = window_title
    self._list_region_ratio = list_region_ratio or (0.10, 0.30, 0.98, 0.88)
    self._window_rect: tuple | None = None
```

修改后的 `capture_list_region`：

```python
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
    screenshot = pyautogui.screenshot(region=region)
    return np.array(screenshot)
```

- [ ] **Step 2: 验证模块可导入**

```bash
python -c "from core.screen_capture import ScreenCapture; sc = ScreenCapture('Apple Music'); assert not hasattr(sc, 'set_custom_region'); print('OK')"
```

---

### Task 6: 更新测试

**Files:**
- Modify: `tests/test_screen_capture.py`

- [ ] **Step 1: 更新 `test_screen_capture.py`**

移除对 `set_custom_region` 和 `_custom_region` 的测试。找到并删除相关测试方法。

如果测试文件中存在测试 `set_custom_region` 的用例，则删除该测试方法和所有引用。

```bash
# 检查哪些测试引用了 set_custom_region
python -m pytest tests/ -v -k "custom_region or set_custom"
```

- [ ] **Step 2: 运行全部测试**

```bash
python -m pytest tests/ -v
```

预期：所有测试 PASS（移除相关测试后数量可能减少）。

---

### Task 7: 最终验证

- [ ] **Step 1: 运行 lint 和类型检查**

```bash
python -m pytest tests/ -v
```

- [ ] **Step 2: 手动验证模块导入链**

```bash
python -c "
from gui.squircle_button import SquircleButton
from gui.settings_popover import SettingsPopover
from gui.main_window import MainWindow
from core.screen_capture import ScreenCapture
print('All imports OK')
"
```

- [ ] **Step 3: 应用启动验证（需要 Apple Music 运行）**

```bash
python main.py
```

预期：无边框窗口显示，浅色 Apple 风格界面，侧边栏 + 网格布局正常渲染。