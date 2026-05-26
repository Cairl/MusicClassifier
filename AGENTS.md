# AGENTS.md

## 项目概述

MusicClassifier 是一个 Windows 上的半自动 Apple Music 歌曲分类工具。截取 Apple Music 窗口，通过 OCR（PaddleOCR）识别歌名，用户从下拉框选择目标歌单，程序自动完成鼠标点击操作将歌曲添加到歌单。

**架构**：截图 → OCR 识别 → 用户选择 → 模拟鼠标点击。四个核心模块通过 `TrackInfo` 数据类串联。所有 UI 自动化操作在后台线程执行，保持 PySide6 GUI 响应。

**技术栈**：Python 3.12, PySide6, PaddleOCR 2.x, PaddlePaddle 2.x, PyAutoGUI, pygetwindow, OpenCV

## 环境配置

- 安装依赖：`pip install -r requirements.txt`
- **关键**：PaddlePaddle 3.x 和 PaddleOCR 3.x 与本项目不兼容。`requirements.txt` 中的版本约束为 `paddleocr>=2.7,<3.0` 和 `paddlepaddle>=2.5,<3.0`，禁止升级超出此范围。
- 本机 Python 路径：`C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe`

## 开发流程

- 运行应用：`python main.py`
- 应用需要 Apple Music 在 Windows 上打开。通过窗口标题 "Apple Music" 查找窗口（可在 `config.json` 中配置）。
- 截图前会自动激活并将 Apple Music 窗口前置。

## 测试说明

- 运行所有测试：`python -m pytest tests/ -v`
- 运行单个测试文件：`python -m pytest tests/test_models.py -v`
- 测试文件位于 `tests/`，命名格式 `test_<模块名>.py`
- 共 18 个测试，分布在 4 个测试文件中
- 测试使用 `unittest.mock` 模拟 `pygetwindow`、`pyautogui` 和 `PaddleOCR`，无需真实窗口或 OCR

## 项目结构

```
MusicClassifier/
├── main.py                  # 入口
├── config.json              # 歌单层级与操作延迟配置
├── requirements.txt         # 依赖及版本约束
├── core/
│   ├── models.py            # TrackInfo, ClassificationResult 数据类
│   ├── screen_capture.py    # 窗口查找、激活、截图
│   ├── ocr_reader.py        # 基于 PaddleOCR 的歌曲和歌单名识别
│   ├── action_executor.py   # 鼠标自动化（点击三点菜单 → 添加到歌单）
│   └── playlist_config.py   # 配置加载、卷/情绪/歌单解析
├── gui/
│   └── main_window.py       # PySide6 主界面，通过 Signal 实现线程安全 UI 更新
└── tests/
    ├── test_models.py
    ├── test_ocr_reader.py
    ├── test_playlist_config.py
    └── test_screen_capture.py
```

## 代码风格

- Python 3.12 类型注解（使用 `X | None` 而非 `Optional[X]`，`tuple[int, int]` 而非 `Tuple[int, int]`）
- 数据模型使用 dataclass（`TrackInfo`、`ClassificationResult`）
- 代码中不加注释，除非明确要求
- `import pyautogui` 和 `import pygetwindow`，禁止使用别名如 `pag`/`pgw`（会破坏 `unittest.mock.patch` 路径）
- 通过 `PySide6.QtCore.Signal` 实现线程安全的 GUI 更新，禁止在后台线程中直接操作 UI

## 关键实现细节

### OCR 列分类

Apple Music 歌单视图有 4 列，X 中心比例边界如下（相对于截图宽度）：

| 列 | X 比例范围 |
|----|-----------|
| 歌名 | 0.00 – 0.28 |
| 艺人 | 0.28 – 0.55 |
| 专辑 | 0.55 – 0.78 |
| 时长/其他 | 0.78+ |

歌名通过二次 OCR 精炼：裁剪图像左侧 30% 并放大 3 倍后重新识别，显著提升歌名完整度。

### 截图区域

默认截图区域比例为 `(0.10, 0.30, 0.98, 0.88)`——Apple Music 窗口的左 10%、上 30%、右 98%、下 88%。目标为歌单列表区域，排除侧边栏和顶部栏。

### 配置格式

`config.json` 定义歌单层级：卷 → 情绪 → 歌单名。每个情绪条目的 `playlist` 字段是 Apple Music「添加到歌单」菜单中显示的精确名称。`tag` 字段为 `VIGOROUS`、`TENSE`、`MELANCHOLY`、`CALM` 之一。

### 操作流程

`ActionExecutor.classify_track()` 执行：点击三点按钮 → 等待 → 点击「添加到歌单」→ 等待 → 点击目标歌单名。每步都通过新的截图 + OCR 定位目标，步骤间有可配置的延迟。

## 常见陷阱

- **PaddlePaddle 3.x 崩溃**：Windows 上出现 `ConvertPirAttribute2RuntimeAttribute` 错误，必须使用 2.x。
- **PaddleOCR 3.x**：移除了 `show_log` 参数，将 `ocr()` 改为 `predict()`，必须使用 2.x。
- **窗口激活**：Windows 上可能静默失败。`activate_window()` 方法有最小化→还原的回退机制。
- **4K 显示器缩放**：`pygetwindow` 返回的窗口坐标可能包含负值（如 -12），这在 Windows 最大化窗口上是正常的。
- **OCR 精度**：最左列的歌名文字较小，经常被部分识别。两遍 OCR（全图 + 歌名区域 3 倍放大）缓解了此问题但不完美。
