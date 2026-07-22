# 情绪分析准确性 / 分析提速 / OCR 框选常驻 — 设计文档

日期：2026-07-22
状态：已获用户确认（三节设计均通过）

## 背景与目标

MusicClassifier 当前存在三个问题：

1. **情绪数值偏移体感**：music2emo（MERT-v1-95M backbone）输出的 valence/arousal 大方向基本正确，但数值与用户体感有系统性偏移。MER 领域 valence 本身难测（论文 R² 远低于 arousal），且通用模型未对齐个体体感。
2. **分析响应慢**：每次分析需写临时 wav 文件 + CPU 推理（秒级），6 秒一跳的离散更新让象限图「走台阶」。
3. **OCR 框选一闪而过**：`_OcrHighlightOverlay` 显示 1500ms 后自动关闭，无法持续确认识别区域。

### 已确认的决策

- 只使用 music2emo 引擎，**彻底删除 librosa 回退路径**
- 机器有 RTX 5070（Blackwell / sm_120），可用 CUDA 加速
- 速度目标：流畅连续更新，不追求极限首结果延迟
- OCR 框选行为：常驻直到下次检测更新或手动停止，**不跟随窗口移动**
- 校准思路：换/升级模型为主，个性化校准���也要

## 总体方案

| 方向 | 方案 |
|---|---|
| 准确性 | A1：引擎内升级 backbone 到 MERT-v1-330M + 个性化校准层（保序回归） |
| 速度 | B1：CUDA 推理 + 二进制帧传输 + 10s 窗 / 2s 步进滑动窗口流水线 |
| OCR 框选 | 去掉自动关闭，overlay 常驻 + 原位更新 |

## 第 1 节：情绪准确性（模型升级 + 个性化校准）

保持「主子进程隔���」架构不动，改动集中在引擎内部和主程序的输出后处理。

### 1.1 music2emo_engine（子进程侧）

- venv 的 torch 升级到 cu128 版本（RTX 5070 / sm_120 硬性要求），模型加载时 `model.cuda()` + float16 推理
- backbone 从 MERT-v1-95M 换成 MERT-v1-330M（`m-a-p/MERT-v1-330M`，首次启动下载约 1.3GB，沿用 `HF_ENDPOINT` 镜像逻辑）
- **回归头兼容策略（风险点）**：若原仓库无 330M 版预训练头，先用 330M 提取嵌入 + 保留现有回归头做兼容性验证；验证不通过则回退为「330M 嵌入 + 用 DEAM 开源权重重训回归头」。实现期实验决定
- `server.py` 协议扩展：输出除 valence/arousal 外附带原始未归一化分数，供校准层使用

### 1.2 新增 `core/mood_calibration.py`（主程序侧）

- `CalibrationStore`：JSON 文件持久化标注样本。每条 = {模型原始 V/A 分数, 用户校正后的 V/A, 时间戳}
- `Calibrator`：样本 >= 10 条时对 valence、arousal 分别拟合保序回归（isotonic，小样本稳定）；样本不足时恒等映射
- 每次新增标注后增量重拟合，结果缓存

### 1.3 标注 UI（gui 侧）

- 象限图上加「校正」入口：点击后弹出 3x3 强度网格（横轴 valence 负到正、纵轴 arousal 低到高），点选当前歌曲真实体感位置即生成一条样本
- 删除 librosa 回退：`_analyze_chunk` 直接走 music2emo；引擎不可用时状态栏报「情绪引擎不可用」，不再静默回退

### 1.4 数据流

`子进程原始分数 → Calibrator 映射 → EMA 平滑 → 象限判定（现有逻辑不变）`

## 第 2 节：分析提速（GPU + 滑动窗口流水线）

### 2.1 进程间传输改造（`core/music2emo_client.py` + `server.py`）

- 废弃「写临时 wav → 传路径」模式
- 新协议：主进程往子进程 stdin 写二进制帧 = 8 字节 header（uint32 采样率 + uint32 帧数，小端）+ float32 PCM 裸数据（单声道）；子进程从 `stdin.buffer` 读取，`np.frombuffer` 进内存
- 响应仍走 stdout JSON 行（带原始分数）；握手版本号 `READY v2`
- 子进程随 `_on_start_toggle` 启动时立即预热（加载模型 + 一次 dummy 前向触发 CUDA 初始化），不再等首次预测

### 2.2 推理流水线（`core/audio_analyzer.py` 重构）

- 定长 10 秒分析窗口、2 秒步进的重叠滑动窗口：每 2 秒取最近 10 秒音频送推理，结果连续流出
- 删除 warmup 窗口递增逻辑（5s 到 15s 阶梯）；缓冲攒满 10 秒前先用可用长度推理（>= 4 秒才开始）
- 推理异步非阻塞：分析线程只负责投递和收结果，子进程推理期间主循环不空等（GPU 单次前向约 100-300ms，2 秒步进足够）
- EMA 参数按新频率重调：`FEATURE_EMA_ALPHA` 从 0.35 提到约 0.5，保持相同时间常数手感；边界检测阈值同步复核
- `ANALYSIS_INTERVAL` 概念废弃，改为 `WINDOW_SECONDS=10` / `HOP_SECONDS=2`
- 频谱条 `get_recent_samples` 路径不变

### 2.3 错误处理

- 子进程崩溃/超时：分析线程捕获后自动重启子进程一次；再失败则状态栏报「情绪引擎已停止」并暂停分析（不回退 librosa）
- CUDA 不可用（torch 版本错误）：启动预热阶段即报错，明确提示重跑 install.bat

## 第 3 节：OCR 框选常驻 + 测试

### 3.1 OCR 框选常驻（`gui/main_window.py`）

- `_OcrHighlightOverlay` 删除 `QTimer.singleShot(_DISPLAY_MS, self.close)`，改为常驻
- overlay 实例复用：新增 `update_rects(rects)` 方法，下次检测时不新建窗口、原位更新并 `update()` 重绘，避免闪烁
- 关闭时机：点击停止按钮；歌曲边���切换后新结果出来前（可选先清后画）；主窗口关闭
- 兜底：Apple Music 窗口失效时隐藏 overlay

### 3.2 测试方案

沿用现有 `tests/` + mock 风格，不碰真实窗口/OCR：

1. `test_mood_calibration.py`（新增）：保序回归拟合、样本不足恒等映射、增量更新、持久化读写
2. `test_audio_analyzer.py`（扩展）：滑动窗口节奏、新 EMA 参数平滑行为、崩溃重启一次后报错、断言不调用 librosa
3. `test_music2emo_client.py`（新增）：二进制帧协议编解码、超时处理、预热流程（mock subprocess）
4. overlay：只测 `update_rects` 状态更新，不测实际渲染

## 风险清单（实现期需验证）

- RTX 5070 + torch cu128 安装组合（install.bat 要改，首次可能踩版本坑）
- MERT-330M 与现有回归头的兼容性
- 2 秒步进 + 校准层叠加后，边界检测阈值可能需实测微调

## 非目标（YAGNI）

- OCR 框选跟随窗口移动（用户明确不需要）
- ONNX/TensorRT 导出（GPU PyTorch 已够快）
- 多模型 ensemble（成本过高）
- librosa 任何形式的保留（用户明确删除回退）
