# UI 比例调整 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 调整 MusicClassifier 主窗口各元素比例，解决卡片过高、按钮过扁、整体偏小的问题。

**Architecture:** 直接修改 `gui/main_window.py` 中的布局参数和 QSS 样式，不涉及架构变更。

**Tech Stack:** PySide6, Python 3.12

---

### Task 1: 调整窗口最小尺寸与主区域边距

**Files:**
- Modify: `gui/main_window.py:140-141`
- Modify: `gui/main_window.py:213-215`

- [ ] **Step 1: 修改窗口最小尺寸**

```python
self.setMinimumSize(int(420 * dpr), int(380 * dpr))
```

- [ ] **Step 2: 修改主区域边距和间距**

```python
main_layout.setContentsMargins(10, 10, 10, 10)
main_layout.setSpacing(8)
```

- [ ] **Step 3: 验证语法**

Run: `python -m py_compile gui/main_window.py`
Expected: 无错误

---

### Task 2: 调整侧边栏尺寸与边距

**Files:**
- Modify: `gui/main_window.py:193-198`
- Modify: `gui/main_window.py:24-27`

- [ ] **Step 1: 修改侧边栏宽度**

```python
sidebar.setFixedWidth(48)
```

- [ ] **Step 2: 修改侧边栏布局边距和间距**

```python
sidebar_layout.setContentsMargins(6, 8, 6, 8)
sidebar_layout.setSpacing(6)
```

- [ ] **Step 3: 修改图标按钮尺寸**

```python
def _make_flat_icon(text: str, color: str, parent=None) -> IconButton:
    btn = IconButton(parent, color=color, icon_text=text)
    btn.setFixedSize(36, 36)
    return btn
```

- [ ] **Step 4: 验证语法**

Run: `python -m py_compile gui/main_window.py`
Expected: 无错误

---

### Task 3: 压缩歌名卡片

**Files:**
- Modify: `gui/main_window.py:217-221`
- Modify: `gui/main_window.py:54-58`

- [ ] **Step 1: 修改卡片内边距**

```python
track_card_layout.setContentsMargins(8, 6, 8, 6)
track_card_layout.setSpacing(2)
```

- [ ] **Step 2: 修改歌名字号 QSS**

```css
QLabel#track_name {
    font-size: 13px;
    font-weight: 700;
    color: #1d1d1f;
}
```

- [ ] **Step 3: 验证语法**

Run: `python -m py_compile gui/main_window.py`
Expected: 无错误

---

### Task 4: 扩张按钮网格

**Files:**
- Modify: `gui/main_window.py:237-243`
- Modify: `gui/main_window.py:80-101`

- [ ] **Step 1: 修改网格间距**

```python
grid.setSpacing(8)
grid.setContentsMargins(0, 0, 0, 0)
```

- [ ] **Step 2: 修改按钮 QSS**

```css
QPushButton#playlist_btn {
    background: #ffffff;
    color: #c7c7cc;
    border: 1px solid rgba(0, 0, 0, 0.05);
    border-radius: 6px;
    padding: 10px 6px;
    font-size: 12px;
    font-weight: 500;
    min-height: 32px;
}
QPushButton#playlist_btn[active="true"] {
    color: #007aff;
    background: rgba(0, 122, 255, 0.06);
    border: 1px solid rgba(0, 122, 255, 0.15);
    font-weight: 600;
}
QPushButton#playlist_btn:hover[active="true"] {
    background: rgba(0, 122, 255, 0.12);
    border: 1px solid rgba(0, 122, 255, 0.25);
}
QPushButton#playlist_btn:pressed[active="true"] {
    background: rgba(0, 122, 255, 0.18);
}
```

- [ ] **Step 3: 验证语法**

Run: `python -m py_compile gui/main_window.py`
Expected: 无错误

---

### Task 5: 运行测试确保无回归

**Files:**
- Test: `tests/`

- [ ] **Step 1: 运行全部测试**

Run: `python -m pytest tests/ -v`
Expected: 44 tests passed

---

### Task 6: 启动应用目视验证

**Files:**
- Run: `main.py`

- [ ] **Step 1: 启动应用**

Run: `python main.py`
Expected: 窗口正常显示，各元素比例协调

- [ ] **Step 2: 检查要点**
  - 窗口尺寸明显大于之前
  - 侧边栏图标更大
  - 歌名卡片更紧凑
  - 按钮更高更宽，不再扁平
  - 整体布局不拥挤
