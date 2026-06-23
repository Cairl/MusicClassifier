# MusicClassifier

> Apple Music 歌曲自动分类工具，结合 PaddleOCR 文字识别与 music2emo（MERT 预训练模型）音频情感分析，根据旋律情绪将歌曲归入四卷十六境播放列表。

## 功能特性

- **实时音频情感分析**：通过系统音频捕获，用 music2emo（基于 MERT 的预训练模型）预测 Arousal-Valence，映射到二维情感象限；引擎不可用时自动降级到 librosa 特征提取
- **四象限情绪模型**：
  - **VIGOROUS**（激昂）：高唤醒 + 高愉悦
  - **TENSE**（紧张）：高唤醒 + 低愉悦
  - **MELANCHOLY**（忧郁）：低唤醒 + 低愉悦
  - **CALM**（平静）：低唤醒 + 高愉悦
- **四卷十六境**：风之卷（季风/飓风/秋风/轻风）、花之卷（春化/绽放/凋零/发芽）、海之卷（碧海/怒海/深海/静海）、月之卷（满月/弦月/残月/新月）
- **PaddleOCR 中文识别**：识别 Apple Music 窗口中的歌曲名、歌手、专辑列，区分表头行与数据行
- **模板匹配定位**：使用 OpenCV 模板匹配快速定位歌曲和菜单按钮位置
- **情感可视化**：实时象限图（2D Arousal-Valence 散点图），显示当前情绪落点与置信度
- **稳定性锁定**：连续分析确认情绪象限后锁定，歌曲边界自动检测并重置
- **自动分类**：分析完成后自动点击目标播放列表，将歌曲归类
- **手动分类**：PlaylistGrid 网格面板，支持 16 个播放列表的一键手动分类
- **屏幕截图库**：模板管理界面，可截取 Apple Music UI 元素作为定位模板

## 系统要求

- **操作系统**：Windows 10/11
- **Apple Music**：需安装并打开 Apple Music 客户端
- **Python**：3.12+
- **GPU**：建议（PaddleOCR 模型推理可加速）

## 技术栈

- **Python 3.12**
- **PySide6**：GUI 框架
- **PaddleOCR + PaddlePaddle**：中文 OCR 文字识别
- **librosa**：音频特征提取（music2emo 不可用时的降级路径）
- **music2emo**（可选）：基于 MERT 的预训练音乐情绪模型，独立子进程运行，提升 valence/arousal 准确度
- **OpenCV (opencv-python)**：模板匹配
- **Pillow**：图像处理
- **pyautogui + pygetwindow**：GUI 自动化
- **process-audio-capture**：系统音频流捕获

## 安装

```bash
git clone <repository-url>
cd MusicClassifier
pip install -r requirements.txt
```

requirements.txt 内容：
```
PySide6>=6.6
paddleocr>=2.7,<3.0
paddlepaddle>=2.5,<3.0
pyautogui>=0.9.54
pygetwindow>=0.0.9
opencv-python>=4.8
Pillow>=10.0
process-audio-capture>=1.0.0
librosa>=0.10
```

### 可选：启用 music2emo 情绪引擎

默认使用 librosa 特征路径。启用 music2emo（基于 MERT 的预训练模型，valence/arousal 更准确，但需额外约 1GB 依赖）：

```bash
music2emo_engine\install.bat
```

该脚本创建独立 venv（Python 3.12）、安装 torch CPU + music2emo 依赖、克隆 music2emo 仓库。首次分析时自动下载 MERT 模型（~400MB，国内可设 `HF_ENDPOINT=https://hf-mirror.com`）。`config.json` 中 `music2emo.enabled` 控制开关，venv 不存在时自动降级到 librosa。

## 使用

### 1. 启动应用

```bash
python main.pyw
```

### 2. 配置识别模板

首次使用需要截取定位模板，确保 Apple Music 界面可被正确识别：

1. 打开 Apple Music
2. 点击侧边栏「截图库」按钮
3. 截取以下模板图像（存入 `templates/` 目录）：

| 模板路径         | 用途         |
|------------------|-------------|
| `position/song_name.png`   | 歌曲名位置定位 |
| `position/artist.png`      | 歌手名位置定位 |
| `position/more_button.png` | 操作按钮定位   |
| `ui/more_button.png`       | 菜单按钮模板   |
| `ui/add_to_playlist.png`   | 添加到播放列表 |
| `playlists/*.png`          | 各播放列表截图 |
| `volumes/*.png`            | 各卷封面截图   |

### 3. 开始分类

1. 在 Apple Music 中打开待分类的歌曲列表
2. 点击「开始」按钮，程序开始：
   - **环境音频捕获**（Warmup 5 秒起步，逐步扩展到 15 秒快照窗口）
   - **弹窗截图识别**当前播放歌曲（PaddleOCR 识别歌名 + 歌手）
   - **实时情绪分析**（每 3 秒采样，EMA 平滑特征，连续 7 次确认后锁定象限）
   - **歌曲切换检测**（情绪突变超过阈值自动识别边界并重置）
   - **自动点击操作**：打开菜单 → 选择目标播放列表 → 完成分类
3. 主题显示在象限图中的实时位置
4. 分析完成后自动标记到对应播放列表

### 4. 手动分类

底部 PlaylistGrid 展示 16 个播放列表按钮，可随时点击手动将当前歌曲归入指定列表。

### 操作按钮

| 按钮        | 功能                    |
|-------------|------------------------|
| 开始/停止   | 开始/停止分类流程        |
| 截图库       | 打开模板管理界面         |
| 各播放列表按钮 | 手动分类到指定播放列表    |

## 项目结构

```
MusicClassifier/
├── main.pyw                    # 应用入口（无控制台窗口）
├── config.json                 # 配置文件（卷、情绪、播放列表、操作延迟等）
├── requirements.txt            # Python 依赖
├── core/
│   ├── models.py               # 数据模型（TrackInfo, ClassificationResult, MoodCoordinates 等）
│   ├── audio_analyzer.py       # librosa 音频分析引擎（特征提取 → EMA 平滑 → 象限映射）
│   ├── audio_capture.py        # 系统音频流捕获管理
│   ├── ocr_reader.py           # PaddleOCR 文字识别（按列分类 / 按位置区域识别）
│   ├── screen_capture.py       # 窗口截图与定位
│   ├── action_executor.py      # 点击与菜单操作执行器
│   ├── template_library.py     # OpenCV 模板匹配库
│   └── playlist_config.py      # 配置加载（卷/情绪/播放列表映射）
├── gui/
│   ├── main_window.py          # 主窗口（整合所有模块）
│   ├── theme.py                # QSS 样式主题
│   ├── sidebar.py              # 侧边栏（开始/停止按钮 + 快捷操作）
│   ├── track_card.py           # 当前歌曲信息卡片
│   ├── quadrant_chart.py       # Arousal-Valence 象限图（实时散点绘图）
│   ├── playlist_grid.py        # 16 宫格播放列表面板（手动分类）
│   ├── screenshot_library.py   # 截图模板管理界面
│   ├── highlight_overlay.py    # 操作高亮覆盖层
│   ├── countdown_overlay.py    # 倒计时覆盖层
│   ├── screenshot_overlay.py   # 截图框选覆盖层
│   └── icons.py                # SVG 图标资源
├── templates/
│   ├── coords.json             # 模板匹配坐标配置
│   ├── position/               # 列位置定位模板
│   │   ├── song_name.png
│   │   ├── artist.png
│   │   └── more_button.png
│   ├── ui/                     # UI 元素模板
│   │   ├── more_button.png
│   │   └── add_to_playlist.png
│   ├── playlists/              # 16 个播放列表名称截图
│   │   ├── 季风.png / 飓风.png / 秋风.png / 轻风.png
│   │   ├── 春化.png / 绽放.png / 凋零.png / 发芽.png
│   │   ├── 碧海.png / 怒海.png / 深海.png / 静海.png
│   │   └── 满月.png / 弦月.png / 残月.png / 新月.png
│   └── volumes/                # 4 卷封面截图
│       ├── 风之卷.png / 花之卷.png / 海之卷.png / 月之卷.png
├── assets/
│   └── icons/                  # SVG 图标
│       ├── play.svg / stop.svg / library.svg
│       ├── add_playlist.svg / done.svg
└── tests/
    ├── test_audio_analyzer.py   # 音频分析单元测试
    └── test_quadrant_chart.py   # 象限图单元测试
```

## 配置说明

`config.json` 关键配置项：

| 配置项                    | 类型    | 说明                           |
|---------------------------|---------|-------------------------------|
| `volumes`                 | array   | 四卷定义，每卷包含 4 种情绪映射    |
| `volumes[].name`          | string  | 卷名（如"风之卷"）               |
| `volumes[].moods`         | array   | 情绪列表                        |
| `volumes[].moods[].name`  | string  | 情绪名（如"季风"）               |
| `volumes[].moods[].tag`   | string  | 情绪标签（VIGOROUS/TENSE/MELANCHOLY/CALM） |
| `volumes[].moods[].playlist` | string | 对应 Apple Music 播放列表名称    |
| `action_delays.after_click_ms` | int | 点击后等待时间（毫秒）           |
| `action_delays.before_screenshot_ms` | int | 截图前等待时间（毫秒）    |
| `action_delays.menu_appear_ms` | int | 菜单出现等待时间（毫秒）         |
| `apple_music_window_title` | string  | Apple Music 窗口标题           |
| `template_matching.threshold` | float | 模板匹配置信度（默认 0.8）      |
| `template_matching.templates_dir` | string | 模板目录（默认 "templates"） |

### 情绪分析参数（`core/audio_analyzer.py` 中可调）

| 参数                          | 默认值    | 说明                     |
|-------------------------------|-----------|--------------------------|
| `ANALYSIS_INTERVAL`           | 6.0 秒    | 分析间隔                  |
| `SNAPSHOT_SECONDS`            | 15.0 秒   | 音频快照窗口最大长度        |
| `WARMUP_START`                | 5.0 秒    | 初始预热窗口               |
| `HISTORY_SIZE`                | 7         | 历史象限记录数              |
| `BOUNDARY_THRESHOLD`          | 0.8       | 未锁定时的歌曲切换检测阈值    |
| `BOUNDARY_THRESHOLD_LOCKED`   | 1.2       | 锁定后的歌曲切换检测阈值     |
| `STABILIZATION_COUNT`         | 4         | 切换后稳定期采样次数         |
| `LOCK_CONFIDENCE`             | 0.6       | 情绪锁定置信度阈值          |
| `FEATURE_EMA_ALPHA`           | 0.35      | 特征 EMA 平滑系数          |

## 许可证

MIT
