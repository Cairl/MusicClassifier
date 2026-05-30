# MusicClassifier UI 重构设计

## 概述

将 MusicClassifier 的 PySide6 界面从当前的下拉框+日志面板布局，重构为现代化的扁平深色主题界面，以行式分组（4行×4列）展示全部 16 个歌单按钮，实现一键分类、自动前进的工作流。

## 布局方案：行式分组（Option B）

选定方案为行式分组：每行代表一个卷（风/花/海/月），每行内 4 个按钮横排对应 4 种情绪（VIGOROUS/TENSE/MELANCHOLY/CALM）。

### 界面结构（自上而下）

1. **歌曲信息区** — 显示当前识别的歌曲名、艺人、专辑。未识别时显示"等待识别..."占位文字。
2. **歌单按钮矩阵** — 5列×5行网格（含标题行和标题列）
   - 第 1 行（列标题）：空白 | VIGOROUS | TENSE | MELANCHOLY | CALM
   - 第 2-5 行：每行首列为卷名标签，后 4 列为歌单按钮
   - 风之卷 | 季风 | 飓风 | 秋风 | 轻风
   - 花之卷 | 春化 | 绽放 | 凋零 | 发芽
   - 海之卷 | 碧海 | 怒海 | 深海 | 静海
   - 月之卷 | 满月 | 弦月 | 残月 | 新月
3. **操作按钮栏** — 水平排列：开始/停止（同一按钮切换状态）、跳过、重新截图

### 不保留的元素

- 操作日志文本框（删除）
- 进度条（删除）
- 下拉框歌单选择器（替换为按钮矩阵）

## 交互流程

1. 用户点击「开始」（按钮文字切换为「停止」）→ 应用激活 Apple Music 窗口 → 截图 → OCR 识别歌曲
2. 歌曲信息显示在顶部
3. 用户点击 16 个歌单按钮中的任意一个
4. 应用立即执行分类操作（点击三点菜单 → 添加到歌单 → 选择目标歌单）
5. 分类完成后自动截图识别下一首歌，回到步骤 2
6. 用户可随时点击「跳过」跳过当前歌曲，或「重新截图」重新识别

### 按钮状态

- 未开始：歌单按钮全部禁用（灰色），「开始」按钮显示"开始"
- 识别中：歌单按钮禁用，「开始」按钮显示"停止"
- 歌曲已识别：歌单按钮启用，可点击
- 分类执行中：歌单按钮禁用，被点击的按钮显示加载状态

### 开始/停止切换

- 「开始」按钮为切换按钮（checkable）
- 点击"开始"后：按钮文字变为"停止"，启动截图-识别-等待分类的循环
- 点击"停止"后：按钮文字恢复为"开始"，设置 `_running = False`，停止自动前进

## 视觉设计

### 主题

- 深色背景（#1a1a2e 系）
- 扁平设计，无阴影、无渐变
- 圆角矩形按钮（border-radius: 4-6px）

### 配色方案

- 背景：深色（#1a1a2e）
- 按钮默认：深蓝灰（#0f3460）
- 按钮悬停：稍亮色
- 按钮点击/激活：强调色
- 卷名标签：强调色文字
- 情绪列标题：低对比度灰色
- 操作按钮：主操作（红色/强调色）、次要操作（紫色/低对比度）

### 字体

- 歌曲名：16px 粗体
- 艺人/专辑：12px 灰色
- 歌单按钮：13px 正常
- 卷名标签：11px 粗体 大写
- 情绪列标题：10px 灰色

## 需要修改的文件

### config.json

修正为 4 卷×4 情绪的完整结构：

- 风之卷：季风(VIGOROUS)、飓风(TENSE)、秋风(MELANCHOLY)、轻风(CALM)
- 花之卷：春化(VIGOROUS)、绽放(TENSE)、凋零(MELANCHOLY)、发芽(CALM)
- 海之卷：碧海(VIGOROUS)、怒海(TENSE)、深海(MELANCHOLY)、静海(CALM)
- 月之卷：满月(VIGOROUS)、弦月(TENSE)、残月(MELANCHOLY)、新月(CALM)

删除「人之卷」。补全「风之卷」缺失的季风和飓风。

### core/playlist_config.py

- 新增 `get_all_moods_flat()` 方法，返回 `list[dict]`，每个条目包含 `volume`, `mood_name`, `tag`, `playlist`
- 保留现有方法以兼容 `ActionExecutor` 的调用链
- `get_playlist_name_from_display()` 简化为直接按 `playlist` 字段查找

### gui/main_window.py

完全重写 `_init_ui()` 方法：

- 移除 `QGroupBox`、`QComboBox`、`QTextEdit`、`QProgressBar`
- 使用 `QGridLayout` 构建 4×4 按钮矩阵
- 每行一个卷，行首添加卷名 `QLabel`
- 列首添加情绪标签 `QLabel`
- 16 个 `QPushButton` 存储为列表，通过 `data` 属性关联 playlist name
- 操作按钮栏使用 `QHBoxLayout`
- 应用全局 QSS 样式表（内嵌在 `main_window.py` 中通过 `app.setStyleSheet()` 或 `self.setStyleSheet()` 设置）实现深色扁平主题
- 保持现有 `_connect_signals()`、`_on_start()`、`_capture_and_detect()` 等逻辑方法不变
- `_on_classify()` 改为接收按钮关联的 playlist name 参数（而非从下拉框读取）
- 分类完成后自动调用 `_capture_and_detect()`（已有此逻辑）

### 不需要修改的文件

- `core/models.py` — TrackInfo 和 ClassificationResult 不变
- `core/screen_capture.py` — 截图逻辑不变
- `core/ocr_reader.py` — OCR 逻辑不变
- `core/action_executor.py` — 操作执行逻辑不变
- `main.py` — 入口不变

## 测试影响

- 现有 4 个测试文件中，UI 相关的测试可能需要更新
- `test_playlist_config.py` 需要更新以反映新的 config 结构（4 卷、删除人之卷）
- 其他 core 模块测试不受影响
