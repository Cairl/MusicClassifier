# UI 全面重构实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 替换 emoji 图标按钮为标准 Qt 图标按钮，重构布局对齐，支持多显示器 DPI 感知

**Architecture:** 新增 `IconButton` 替代 `SquircleButton`，重写 `MainWindow._init_ui` 布局逻辑，移除 `Qt.WA_TranslucentBackground`

**Tech Stack:** Python 3.12, PySide6, QSS

---

### Task 1: 创建 IconButton 组件

**Files:**
- Create: `gui/icon_button.py`
- Delete: `gui/squircle_button.py`

- [ ] **Step 1: 创建 `gui/icon_button.py`**

```python
from PySide6.QtWidgets import QToolButton, QStyle
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor


class IconButton(QToolButton):
    def __init__(self, parent=None, color="#007aff", icon_style=None):
        super().__init__(parent)
        self._base_color = QColor(color)
        self.setFixedSize(48, 48)
        self.setCursor(Qt.PointingHandCursor)
        if icon_style is not None:
            icon = self.style().standardIcon(icon_style)
            self.setIcon(icon)
            self.setIconSize(QSize(24, 24))
        self.setStyleSheet(self._build_qss(color))

    def _build_qss(self, color: str) -> str:
        hover = QColor(color).lighter(108).name()
        pressed = QColor(color).darker(120).name()
        return f"""
            QToolButton {{
                background-color: {color};
                border: none;
                border-radius: 12px;
                padding: 4px;
            }}
            QToolButton:hover {{
                background-color: {hover};
            }}
            QToolButton:pressed {{
                background-color: {pressed};
            }}
            QToolButton:disabled {{
                background-color: #c7c7cc;
            }}
        """

    def setColor(self, color: str):
        self._base_color = QColor(color)
        self.setStyleSheet(self._build_qss(color))
        if self.icon():
            self.setIcon(self.style().standardIcon(self._current_icon_style))
```

- [ ] **Step 2: 删除 `gui/squircle_button.py`**

```bash
rm gui/squircle_button.py
```

- [ ] **Step 3: Commit**

```bash
git add gui/icon_button.py
git rm gui/squircle_button.py
git commit -m "feat: add IconButton, remove SquircleButton"
```

---

### Task 2: 修改 MainWindow 导入和初始化

**Files:**
- Modify: `gui/main_window.py:1-25`

- [ ] **Step 1: 替换导入**

将 `from gui.squircle_button import SquircleButton` 替换为 `from gui.icon_button import IconButton`。

同时添加 `QStyle` 导入：

```python
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QMessageBox,
)
```

改为：

```python
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QMessageBox, QStyle,
)
```

- [ ] **Step 2: Commit**

```bash
git add gui/main_window.py
git commit -m "refactor: replace SquircleButton import with IconButton"
```

---

### Task 3: 重写 MainWindow._init_ui

**Files:**
- Modify: `gui/main_window.py:143-292`

- [ ] **Step 1: 移除 `Qt.WA_TranslucentBackground`**

在 `_init_ui` 中删除：
```python
self.setAttribute(Qt.WA_TranslucentBackground)
```

- [ ] **Step 2: DPI 感知最小尺寸**

在 `_init_ui` 中 `setMinimumSize` 之前添加：

```python
screen = QGuiApplication.primaryScreen()
dpr = screen.devicePixelRatio() if screen else 1.0
self.setMinimumSize(int(560 * dpr), int(500 * dpr))
```

同时需要导入 `QGuiApplication`：

```python
from PySide6.QtCore import Signal, QObject, Qt, QPoint, QEvent
```

改为：

```python
from PySide6.QtCore import Signal, QObject, Qt, QPoint, QEvent, QGuiApplication
```

- [ ] **Step 3: 替换 SquircleButton 为 IconButton**

将：
```python
self._start_btn = SquircleButton("", color="#007aff", icon_text="\u25b6")
```
改为：
```python
self._start_btn = IconButton(self, color="#007aff", icon_style=QStyle.SP_MediaPlay)
```

将：
```python
self._settings_btn = SquircleButton("", color="#8e8e93", icon_text="\u2699")
```
改为：
```python
self._settings_btn = IconButton(self, color="#8e8e93", icon_style=QStyle.SP_FileDialogDetailedView)
```

- [ ] **Step 4: 修改侧边栏宽度**

将：
```python
sidebar.setFixedWidth(60)
```
改为：
```python
sidebar.setFixedWidth(72)
```

- [ ] **Step 5: 修改按钮状态更新方法**

将 `_on_start_toggle` 中的：
```python
self._start_btn.setColor("#007aff")
self._start_btn.setIconText("\u25b6")
```
改为：
```python
self._start_btn.setColor("#007aff")
self._start_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
```

将：
```python
self._start_btn.setColor("#ff3b30")
self._start_btn.setIconText("\u23f9")
```
改为：
```python
self._start_btn.setColor("#ff3b30")
self._start_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
```

- [ ] **Step 6: 重构歌单网格布局**

重写网格布局部分（约 252-289 行），确保：
- 卷名完整显示
- 列等宽
- 标签与按钮对齐

替换为：

```python
        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setSpacing(8)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setColumnStretch(0, 0)
        for col in range(1, 5):
            grid.setColumnStretch(col, 1)

        grid.addWidget(QLabel(""), 0, 0)
        for col, tag_label in enumerate(TAG_LABELS, start=1):
            header = QLabel(tag_label)
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

            vol_moods = {m["tag"]: m for m in moods if m["volume"] == volume_name}
            for col_idx, tag in enumerate(TAG_ORDER, start=1):
                if tag in vol_moods:
                    mood_info = vol_moods[tag]
                    btn = QPushButton(mood_info["mood_name"])
                    btn.setObjectName("playlist_btn")
                    btn.setProperty("active", "false")
                    btn.clicked.connect(partial(
                        self._on_classify, mood_info["playlist"], volume_name
                    ))
                    self._playlist_buttons.append(btn)
                    grid.addWidget(btn, row_idx, col_idx)
```

- [ ] **Step 7: Commit**

```bash
git add gui/main_window.py
git commit -m "refactor: rewrite MainWindow layout with IconButton, DPI scaling, aligned grid"
```

---

### Task 4: 最大化时禁用拖动

**Files:**
- Modify: `gui/main_window.py:310-319`

- [ ] **Step 1: 修改 mousePressEvent**

将：
```python
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            local_y = event.position().toPoint().y()
            if local_y <= 40:
                self._drag_pos = event.globalPosition().toPoint()
        super().mousePressEvent(event)
```
改为：
```python
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and not self.isMaximized():
            local_y = event.position().toPoint().y()
            if local_y <= 40:
                self._drag_pos = event.globalPosition().toPoint()
        super().mousePressEvent(event)
```

- [ ] **Step 2: Commit**

```bash
git add gui/main_window.py
git commit -m "fix: disable title bar drag when maximized"
```

---

### Task 5: 运行测试

**Files:**
- Test: `tests/`

- [ ] **Step 1: 运行全部测试**

```bash
python -m pytest tests/ -v
```

Expected: 44 passed

- [ ] **Step 2: 如有失败，修复**

检查失败原因，可能是 `squircle_button` 的导入残留或 `IconButton` 的接口差异。

- [ ] **Step 3: Commit**

```bash
git add .
git commit -m "test: verify UI redesign passes all tests"
```

---

## Self-Review

**Spec coverage:**
- IconButton 替代 SquircleButton ✅ Task 1
- 移除 Qt.WA_TranslucentBackground ✅ Task 3 Step 1
- DPI 感知最小尺寸 ✅ Task 3 Step 2
- 布局对齐（卷名完整、列等宽）✅ Task 3 Step 6
- 最大化禁用拖动 ✅ Task 4

**Placeholder scan:** 无 TBD/TODO，所有步骤含完整代码。

**Type consistency:** `IconButton` 的 `setColor` 方法签名与 `SquircleButton` 一致，替换后调用方无需修改。
