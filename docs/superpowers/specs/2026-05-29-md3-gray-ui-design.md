# MD3 淡灰色系 UI 重构设计

## 目标

将 MusicClassifier 界面从当前 Apple 风格重构为 Material Design 3 淡灰色系风格，视觉更柔和舒适。

## 约束

- Windows 原生窗口框架不变
- 按钮使用 Windows 原生 QPushButton
- 窗口宽度保持 240px（DPI 缩放前），高度自适应
- 不使用 `Qt.WA_TranslucentBackground`
- 不使用自定义 `paintEvent`（DPI 缩放兼容性）
- 所有固定像素值需乘以 `devicePixelRatio`

## 色板

| 角色 | 色值 | 用途 |
|------|------|------|
| Surface | `#fafafa` | 窗口背景、侧边栏背景 |
| Card | `#ffffff` | 曲目卡片背景 |
| Button Fill | `#e8eaed` | 歌单按钮默认填充 |
| Icon Fill | `#e0e0e0` | 侧边栏图标按钮填充 |
| Hover | `#dadce0` | 按钮悬停态 |
| Pressed | `#c4c7c9` | 按钮按下态 |
| Disabled Fill | `#f1f3f4` | 禁用态填充 |
| Disabled Text | `#9aa0a6` | 禁用态文字 |
| Secondary | `#5f6368` | 副文字、标签、表头 |
| On-Surface | `#202124` | 主文字、卷名标签 |
| On-Surface Variant | `#80868b` | 三级文字（专辑名等） |

## 组件规格

### 窗口背景

- 当前：`#f3f3f3`
- MD3：`#fafafa`

### 侧边栏

- 当前：白底 `#ffffff` + 1px 右边框 `rgba(0,0,0,0.06)`
- MD3：同窗口背景 `#fafafa`，无边框
- 宽度保持 48px

### 图标按钮（播放/设置）

- 当前：36px 圆形 + 1.5px 描边 + 透明背景
- MD3：28px 圆形 + `#e0e0e0` 填充 + 无描边
- 两个按钮完全相同尺寸和风格
- 播放按钮图标色 `#424242`，设置按钮图标色 `#424242`
- 悬停：`#dadce0` 填充
- 按下：`#c4c7c9` 填充
- 激活态（运行中）：`#c4c7c9` 填充（视觉区分但不突兀）

### 曲目卡片

- 当前：白底 + 1px 边框 `rgba(0,0,0,0.06)` + 8px 圆角
- MD3：白底 + 无边框 + 12px 圆角 + 轻阴影 `0 1px 2px rgba(0,0,0,0.05)`
- 内边距：8px 10px

### 歌单按钮

- 当前：`#e5e5ea` 填充 + 3px 圆角 + `padding: 6px 4px` + `min-height: 28px`
- MD3：`#e8eaed` 填充 + 8px 圆角 + `padding: 6px 4px` + `min-height: 28px`
- 悬停：`#dadce0`
- 按下：`#c4c7c9`
- 禁用：`#f1f3f4` 填充 + `#9aa0a6` 文字

### 文字样式

| 元素 | 当前 | MD3 |
|------|------|-----|
| 曲目名 | 13px/700 `#1d1d1f` | 13px/500 `#202124` |
| 专辑名 | 11px `#8e8e93` | 11px `#80868b` |
| 卷标签 | 10px/600 `#007aff` | 10px/600 `#5f6368` |
| 表头 | 9px/600 `#8e8e93` | 9px/600 `#5f6368` |
| 卷名 | 11px/600 `#1d1d1f` | 11px/600 `#202124` |
| 歌单按钮 | 11px `#1d1d1f` | 11px `#202124` |

### 网格间距

- 当前：2px
- MD3：4px（更宽松的呼吸感）

## 涉及文件

1. `gui/main_window.py` — QSS 样式表 `LIGHT_FLAT_QSS`、`_make_circle_icon` 函数、布局间距
2. `gui/icon_button.py` — `IconButton` 类样式（如仍被引用）
3. `gui/settings_popover.py` — 弹出菜单样式
4. `gui/capture_wizard.py` — 向导对话框样式
5. `gui/screenshot_overlay.py` — 截图覆盖层工具栏样式

## 不变项

- 窗口框架：Windows 原生
- 布局结构：侧边栏 + 主区域（曲目卡片 + 网格）
- 功能逻辑：所有交互行为不变
- `core/` 模块：不涉及
