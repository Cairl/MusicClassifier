# UI 全面重构设计文档

## 背景

当前 MusicClassifier GUI 存在三个核心视觉问题：
1. 按钮使用 emoji 字符（▶/⚙）作为图标，自定义 `paintEvent` 绘制的 squircle 形状在低 DPI 下边缘发虚
2. 歌单网格布局元素未对齐：卷名仅显示首字、列宽不一致、标签行与按钮行错位
3. 跨显示器/多 DPI 环境下窗口尺寸失衡：`Qt.WA_TranslucentBackground` 可能引发渲染异常，所有尺寸硬编码

## 目标

- 替换 emoji 图标为 Qt 标准图标/SVG 路径，移除自定义 `paintEvent`
- 重构布局使卷名、情绪标签、歌单按钮严格对齐
- 支持多显示器 DPI 感知，窗口尺寸动态适配

## 架构变更

### 删除的组件

| 组件 | 原因 |
|------|------|
| `gui/squircle_button.py` | 自定义 `paintEvent` 是 DPI 和渲染问题根源，由 `IconButton` 替代 |

### 新增的组件

| 组件 | 职责 |
|------|------|
| `gui/icon_button.py` | 基于 `QToolButton` + `QIcon` 的圆角矩形图标按钮，QSS 控制状态样式 |

### 修改的组件

| 组件 | 变更内容 |
|------|---------|
| `gui/main_window.py` | 移除 `Qt.WA_TranslucentBackground`；重写 `_init_ui` 布局；DPI 感知尺寸计算；最大化时禁用拖动 |
| `main.py` | 保留 `SetProcessDpiAwareness(2)`，无需变更 |

## 详细设计

### IconButton

继承 `QToolButton`，使用 Qt 内置标准图标：
- 播放：`QStyle.SP_MediaPlay`
- 停止：`QStyle.SP_MediaStop`
- 设置：`QStyle.SP_FileDialogDetailedView`

尺寸 48×48（逻辑像素，Qt 自动按 DPI 缩放），`border-radius: 12px`。
状态样式通过 QSS 伪类实现，不使用自定义 `paintEvent`。

颜色映射：
- 主色（播放）：`#007aff`
- 停止：`#ff3b30`
- 设置：`#8e8e93`
- 悬浮：基础色亮度 +8%
- 按下：基础色亮度 -12%

### 布局对齐

侧边栏宽度从固定 60px 改为 72px（容纳 48px 按钮 + 12px 边距 + 间距）。

歌单网格使用 `QGridLayout`，结构如下：
```
      [空]    [活力]   [紧张]   [忧郁]   [平静]
风之卷  [季风]  [飓风]   [秋风]   [轻风]
花之卷  [春化]  [绽放]   [凋零]   [发芽]
```

约束：
- 第 0 列（卷名）`setColumnStretch(0, 0)`，自适应内容宽度，完整显示卷名
- 第 1-4 列（情绪列）`setColumnStretch(1-4, 1)`，等分剩余宽度
- `setColumnMinimumWidth` 确保按钮文字不被截断
- 卷名标签 `AlignRight | AlignVCenter`
- 情绪标签 `AlignCenter`
- 按钮文字 `AlignCenter`

窗口边距统一为 12px。

### 跨显示器适配

移除 `Qt.WA_TranslucentBackground`，窗口背景使用纯色 `#f2f2f7`。

最小尺寸计算：
```python
screen = QGuiApplication.primaryScreen()
dpr = screen.devicePixelRatio() if screen else 1.0
self.setMinimumSize(int(560 * dpr), int(500 * dpr))
```

最大化时禁用自定义标题栏拖动：在 `mousePressEvent` 中检查 `self.isMaximized()`，若为真则不设置 `_drag_pos`。

## 数据流

无变更。`MainWindow` 的信号/槽机制、后台线程工作流保持不变。

## 错误处理

- `IconButton` 若请求的 Qt 标准图标不可用，回退到文字标签
- DPI 获取失败时 `dpr` 默认为 1.0

## 测试策略

- 运行现有 44 个测试确保无回归
- 手动验证：在 100% 和 150% DPI 显示器上检查窗口尺寸和按钮渲染
- 手动验证：窗口最大化后点击标题栏绿点可还原
