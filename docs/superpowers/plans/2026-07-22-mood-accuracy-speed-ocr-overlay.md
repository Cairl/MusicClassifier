# 情绪准确性 + 分析提速 + OCR 框选常驻 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 升级 music2emo 引擎到 GPU 全内存推理 + 滑动窗口分析流水线 + 个性化情绪校准层 + OCR 框选常驻显示。

**Architecture:** 保持主子进程隔离：engine venv 内 server.py 重写为 v2 协议（stdin 二进制帧 + 全模型常驻预热 + 全内存推理）；主进程 analyzer 改为 10s 窗 / 2s 步进滑窗，删除 librosa 回退；新增校准模块（保序回归）和象限图 3x3 校正 UI；OCR overlay 去掉自动关闭改为常驻复用。

**Tech Stack:** Python 3.12, PySide6, torch 2.7.1+cu128 (engine venv), MERT-v1-95M, scikit-learn (isotonic regression), pytest + unittest.mock。

**Spec:** `docs/superpowers/specs/2026-07-22-mood-accuracy-speed-ocr-overlay-design.md`

## Global Constraints

- PaddlePaddle `<3.0`、PaddleOCR `>=2.7,<3.0` 版本钉死，不得升级
- 主程序 Python: `C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe`
- 测试命令: `C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/ -v`
- 类型标注用 `X | None`、`tuple[int, int]`，不用 `Optional`/`Tuple`
- 代码里不写注释（除非用户明确要求）；docstring 允许保留
- `import pyautogui` / `import pygetwindow` 不起别名（mock.patch 路径依赖）
- 后台线程更新 GUI 必须走 `PySide6.QtCore.Signal`
- UI 颜色/字号一律用 `gui/theme.py` 的 token，不硬编码 `#fafafa` 等
- 不使用 emoji（用户全局规则）
- 只提交本任务相关文件；工作区存在用户的其他未提交改动（`core/audio_analyzer.py` M、旧测试删除、`tests/test_audio_analyzer_mood_fix.py` 新增），`git add` 时必须点名具体文件
- 禁止 `git push`

---

### Task 1: 引擎 venv 升级 torch cu128 + verify.py 显示设备

RTX 5070 是 sm_120（Blackwell），torch < 2.7 没有对应 kernel，必须用 cu128 构建。

**Files:**
- Modify: `music2emo_engine/install.bat`
- Modify: `music2emo_engine/requirements-engine.txt`
- Modify: `music2emo_engine/verify.py`

**Interfaces:**
- Produces: 引擎 venv 内 `torch.cuda.is_available() == True`；`verify.py` 输出新增 `device = cuda|cpu` 与 `server = READY v2` 两行（Task 2/3 落地后才有 v2，本任务先验证 torch 安装）

- [ ] **Step 1: 修改 requirements-engine.txt**

只改前两行，其余不动：

```
torch==2.7.1
torchaudio==2.7.1
transformers==4.44.0
mir_eval
pretty_midi==0.2.10
music21==9.3.0
omegaconf==2.3.0
hydra-core==1.3.2
nnAudio==0.3.1
chordparser==0.4.2
numpy==1.26.4
numba==0.60.0
llvmlite==0.43.0
librosa==0.10.2.post1
scikit_learn==1.6.1
pandas==2.2.3
tqdm
PyYAML
soundfile
setuptools==75.0.0
```

- [ ] **Step 2: 修改 install.bat 的 torch 安装段**

把第 20-28 行（`[2/4]` 段）替换为：

```bat
echo [2/4] Installing torch 2.7.1 CUDA 12.8 build (RTX 50 series)...
"%PIP%" install -U torch==2.7.1 torchaudio==2.7.1 --index-url https://download.pytorch.org/whl/cu128
if errorlevel 1 goto :torchretry
goto :torchdone

:torchretry
echo [WARN] cu128 index failed. Falling back to CPU build...
"%PIP%" install -U torch==2.7.1 torchaudio==2.7.1 --index-url https://download.pytorch.org/whl/cpu
if errorlevel 1 goto :depfail
```

注意 `-U` 参数：已有 venv 里装着 torch 2.3.1 CPU 版，必须升级覆盖。

- [ ] **Step 3: 运行 install.bat**

Run: `music2emo_engine\install.bat`
Expected: 输出 `Setup complete.`；torch 从 cu128 index 下载（约 2.5GB，耗时较长）

- [ ] **Step 4: 验证 CUDA 在引擎 venv 内可用**

Run: `music2emo_engine\.venv\Scripts\python.exe -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'no-gpu')"`
Expected: 打印 `2.7.1+cu128 True NVIDIA GeForce RTX 5070`（或等价）
若打印 `no-gpu`：检查 nvidia 驱动版本（需 >= 550），然后重跑 install.bat；仍失败则暂停并报告，不要继续后续任务

- [ ] **Step 5: Commit**

```bash
git add music2emo_engine/install.bat music2emo_engine/requirements-engine.txt
git commit -m "chore(engine): upgrade torch to 2.7.1+cu128 for RTX 5070"
```

---

### Task 2: server.py v2 — 全模型常驻 + 全内存推理

现状（`music2emo_engine/server.py`）每次 predict 调用 repo 的 `Music2emo.predict()`，它会：删建 temp 目录、MERT 特征写 npy 再读回、**每次从磁盘重载 BTC 和弦模型**、music21 调式分析、反复读 json。v2 改为启动时全部预加载，推理全内存（仅和弦链的 .lab/.midi 保留临时文件，因为 mir_eval/music21 要文件路径，属于引擎本地 IO）。

协议 v2：stdin 二进制帧 = 8 字节 header `struct "<II"`（uint32 采样率 + uint32 帧数，小端）+ `帧数*4` 字节 float32 单声道 PCM；`帧数 == 0xFFFFFFFF` 表示 EXIT。响应仍是 stdout JSON 行。

**Files:**
- Modify: `music2emo_engine/server.py`（整体重写）
- Modify: `music2emo_engine/verify.py`（Step 5 改）

**Interfaces:**
- Consumes: Task 1 的 cu128 torch
- Produces: 握手行 `READY v2`；响应 JSON `{"valence": float(1-9), "arousal": float(1-9), "moods": list[str], "device": "cuda"|"cpu"}` 或 `{"error": str}`。Task 3 的 client 依赖此协议；`M2E_MERT_MODEL` 环境变量可覆盖 MERT backbone（Task 8 用）

- [ ] **Step 1: 重写 server.py**

完整替换为：

```python
"""music2emo inference server v2.

Long-lived child process inside the dedicated engine venv. All models are
preloaded once at startup; inference runs fully in memory on GPU.

Protocol v2 (binary on stdin, JSON lines on stdout):
  - server prints "READY v2" after all models are loaded and warmed up
  - request: 8-byte header struct "<II" (sample_rate, frame_count,
    little-endian) followed by frame_count*4 bytes of float32 mono PCM
  - frame_count == 0xFFFFFFFF shuts the server down cleanly
  - response: one JSON line {"valence","arousal","moods","device"} or {"error"}
  - M2E_MERT_MODEL env var overrides the MERT backbone name
"""

import json
import os
import struct
import sys
import tempfile
import types

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.join(_HERE, "music2emo_repo")

os.chdir(REPO_DIR)
sys.path.insert(0, REPO_DIR)

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

sys.modules.setdefault("gradio", types.ModuleType("gradio"))
sys.modules.setdefault("pytorch_lightning", types.ModuleType("pytorch_lightning"))

EXIT_FRAME_COUNT = 0xFFFFFFFF
RESAMPLE_RATE = 24000
SEGMENT_SECONDS = 30
MERT_LAYERS = [5, 6]
EMBEDDING_DIM = 1536
HEADER = struct.Struct("<II")


class Engine:
    def __init__(self):
        import numpy as np
        import torch
        from model.linear_mt_attn_ck import FeedforwardModelMTAttnCK
        from utils.btc_model import BTC_model
        from utils.hparams import HParams
        from utils.mert import FeatureExtractorMERT
        from utils.mir_eval_modules import idx2voca_chord

        self._np = np
        self._torch = torch
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        mert_name = os.environ.get("M2E_MERT_MODEL", "m-a-p/MERT-v1-95M")
        self.mert = FeatureExtractorMERT(model_name=mert_name, device=self.device, sr=RESAMPLE_RATE)

        self.head = FeedforwardModelMTAttnCK(
            input_size=EMBEDDING_DIM,
            output_size_classification=56,
            output_size_regression=2,
        )
        ckpt = torch.load("saved_models/J_all.ckpt", map_location=self.device, weights_only=False)
        state_dict = {k.replace("model.", ""): v for k, v in ckpt["state_dict"].items()}
        model_keys = set(self.head.state_dict().keys())
        self.head.load_state_dict({k: v for k, v in state_dict.items() if k in model_keys})
        self.head.to(self.device).eval()

        self.btc_config = HParams.load("./inference/data/run_config.yaml")
        self.btc_config.feature["large_voca"] = True
        self.btc_config.model["num_chords"] = 170
        self.btc = BTC_model(config=self.btc_config.model).to(self.device)
        btc_ckpt = torch.load("./inference/data/btc_model_large_voca.pt", map_location=self.device)
        self.btc_mean = btc_ckpt["mean"]
        self.btc_std = btc_ckpt["std"]
        self.btc.load_state_dict(btc_ckpt["model"])
        self.btc.eval()
        self.idx_to_chord = idx2voca_chord()

        with open("inference/data/chord.json") as f:
            self.chord_to_idx = json.load(f)
        with open("inference/data/chord_root.json") as f:
            self.chord_root_dic = json.load(f)
        with open("inference/data/chord_attr.json") as f:
            self.chord_attr_dic = json.load(f)

        self.tag_list = [t.replace("mood/theme---", "")
                         for t in list(np.load("./inference/data/tag_list.npy"))[127:]]

    def predict_pcm(self, pcm, sr: int) -> dict:
        np = self._np
        torch = self._torch

        waveform = torch.from_numpy(np.ascontiguousarray(pcm, dtype=np.float32))
        if sr != RESAMPLE_RATE:
            import torchaudio.transforms as T
            waveform = T.Resample(sr, RESAMPLE_RATE)(waveform)

        mert_vec = self._mert_embedding(waveform)
        chords, root, attr, mode = self._chord_key_features(waveform)

        inputs = {
            "x_mert": torch.from_numpy(mert_vec).unsqueeze(0),
            "x_chord": chords.unsqueeze(0),
            "x_chord_root": root.unsqueeze(0),
            "x_chord_attr": attr.unsqueeze(0),
            "x_key": mode.unsqueeze(0),
        }
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        with torch.no_grad():
            classification_output, regression_output = self.head(inputs)
        probs = torch.sigmoid(classification_output).squeeze().tolist()
        moods = [self.tag_list[i] for i, p in enumerate(probs) if p > 0.5]
        valence, arousal = regression_output.squeeze().tolist()
        return {
            "valence": float(valence),
            "arousal": float(arousal),
            "moods": moods,
            "device": "cuda" if self.device.type == "cuda" else "cpu",
        }

    def _mert_embedding(self, waveform):
        np = self._np
        torch = self._torch
        seg_samples = SEGMENT_SECONDS * RESAMPLE_RATE
        if waveform.numel() <= seg_samples:
            segments = [waveform]
        else:
            segments = [waveform[i:i + seg_samples]
                        for i in range(0, waveform.numel(), seg_samples)]
        embs = []
        for seg in segments:
            inputs = self.mert.processor(seg.float(), sampling_rate=RESAMPLE_RATE,
                                         return_tensors="pt")
            inputs = inputs.to(self.device)
            with torch.no_grad():
                outputs = self.mert.model(**inputs, output_hidden_states=True)
            layers = torch.stack(outputs.hidden_states).squeeze()[1:, :, :].unsqueeze(0)
            feats = layers.mean(dim=2).cpu().numpy()
            embs.append(np.concatenate([feats[:, i, :] for i in MERT_LAYERS], axis=1).squeeze())
        return np.mean(np.array(embs), axis=0).astype(np.float32)

    def _chord_key_features(self, waveform):
        np = self._np
        torch = self._torch
        import librosa
        import mir_eval
        import pretty_midi as pm
        from music21 import converter

        cfg = self.btc_config
        sr = cfg.mp3["song_hz"]
        samples = waveform.numpy()
        if sr != RESAMPLE_RATE:
            samples = librosa.resample(samples, orig_sr=RESAMPLE_RATE, target_sr=sr)

        inst = int(sr * cfg.mp3["inst_len"])
        feature = None
        pos = 0
        while pos + inst <= len(samples):
            tmp = librosa.cqt(samples[pos:pos + inst], sr=sr,
                              n_bins=cfg.feature["n_bins"],
                              bins_per_octave=cfg.feature["bins_per_octave"],
                              hop_length=cfg.feature["hop_length"])
            feature = tmp if feature is None else np.concatenate((feature, tmp), axis=1)
            pos += inst
        if pos < len(samples):
            tmp = librosa.cqt(samples[pos:], sr=sr,
                              n_bins=cfg.feature["n_bins"],
                              bins_per_octave=cfg.feature["bins_per_octave"],
                              hop_length=cfg.feature["hop_length"])
            feature = tmp if feature is None else np.concatenate((feature, tmp), axis=1)
        feature = np.log(np.abs(feature) + 1e-6)

        feature = ((feature.T - self.btc_mean) / self.btc_std).astype(np.float32)
        time_unit = cfg.mp3["inst_len"] / cfg.model["timestep"]
        n_timestep = cfg.model["timestep"]
        num_pad = n_timestep - (feature.shape[0] % n_timestep)
        feature = np.pad(feature, ((0, num_pad), (0, 0)), mode="constant")
        num_instance = feature.shape[0] // n_timestep

        lines = []
        start_time = 0.0
        with torch.no_grad():
            feat_t = torch.tensor(feature).unsqueeze(0).to(self.device)
            for t in range(num_instance):
                attn_out, _ = self.btc.self_attn_layers(
                    feat_t[:, n_timestep * t:n_timestep * (t + 1), :])
                prediction, _ = self.btc.output_layer(attn_out)
                prediction = prediction.squeeze()
                for i in range(n_timestep):
                    if t == 0 and i == 0:
                        prev_chord = prediction[i].item()
                        continue
                    if prediction[i].item() != prev_chord:
                        lines.append((start_time, time_unit * (n_timestep * t + i),
                                      self.idx_to_chord[prev_chord]))
                        start_time = time_unit * (n_timestep * t + i)
                        prev_chord = prediction[i].item()
                    if t == num_instance - 1 and i + num_pad == n_timestep:
                        if start_time != time_unit * (n_timestep * t + i):
                            lines.append((start_time, time_unit * (n_timestep * t + i),
                                          self.idx_to_chord[prev_chord]))
                        break
        if not lines:
            lines = [(0.0, time_unit, "N")]

        workdir = tempfile.mkdtemp(prefix="m2e_")
        lab_path = os.path.join(workdir, "clip.lab")
        with open(lab_path, "w") as f:
            for s, e, c in lines:
                f.write("%.3f %.3f %s\n" % (s, e, c))

        starts, ends, pitchs = [], [], []
        intervals, chords_lab = mir_eval.io.load_labeled_intervals(lab_path)
        for p in range(12):
            for i, (interval, chord) in enumerate(zip(intervals, chords_lab)):
                root_num, relative_bitmap, _ = mir_eval.chord.encode(chord)
                tmp_label = mir_eval.chord.rotate_bitmap_to_root(relative_bitmap, root_num)[p]
                if i == 0:
                    start_time = interval[0]
                    label = tmp_label
                    continue
                if tmp_label != label:
                    if label == 1.0:
                        starts.append(start_time), ends.append(interval[0]), pitchs.append(p + 48)
                    start_time = interval[0]
                    label = tmp_label
                if i == len(intervals) - 1 and label == 1.0:
                    starts.append(start_time), ends.append(interval[1]), pitchs.append(p + 48)

        midi = pm.PrettyMIDI()
        instrument = pm.Instrument(program=0)
        for start, end, pitch in zip(starts, ends, pitchs):
            instrument.notes.append(pm.Note(velocity=120, pitch=pitch, start=start, end=end))
        midi.instruments.append(instrument)
        midi_path = lab_path.replace(".lab", ".midi")
        midi.write(midi_path)

        try:
            key_signature = str(converter.parse(midi_path).analyze("key"))
        except Exception:
            key_signature = "None"
        key_parts = key_signature.split()
        key_signature = key_parts[0].replace("-", "b") if key_parts[0] != "None" else "None"
        key_type = key_parts[1] if len(key_parts) > 1 else "major"

        mode_signatures = ["major", "minor"]
        mode_to_idx = {m: i for i, m in enumerate(mode_signatures)}
        if key_signature == "None":
            mode = "major"
        else:
            mode = key_signature.split()[-1]
        mode_idx = mode_to_idx.get(mode, 0)

        shift = 0
        if key_signature != "None" and len(key_signature) >= 1:
            pitch_num_dic = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5,
                             "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}
            minor_major_dic2 = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#"}
            key = minor_major_dic2.get(key_signature, key_signature)
            if key in pitch_num_dic:
                shift = pitch_num_dic[key] if key_type == "major" else (pitch_num_dic[key] + 3) % 12

        pitch_class = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        encoded, encoded_root, encoded_attr = [], [], []
        for s, e, chord in lines:
            c = chord
            if c not in ("N", "X"):
                parts = c.split(":")
                root_name = parts[0]
                if root_name in pitch_num_dic:
                    new_root = pitch_class[(pitch_num_dic[root_name] - shift) % 12]
                    c = new_root + (":" + parts[1] if len(parts) > 1 else "")
            if c in ("N", "X"):
                c = "N"
            arr = c.split(":")
            root_id = self.chord_root_dic.get(arr[0], self.chord_root_dic.get("N", 0))
            attr_id = 0
            if len(arr) == 2:
                attr_id = self.chord_attr_dic.get(arr[1], 0)
            elif arr[0] not in ("N", "X"):
                attr_id = 1
            encoded_root.append(root_id)
            encoded_attr.append(attr_id)
            encoded.append(self.chord_to_idx.get(c, self.chord_to_idx.get("N", 0)))

        max_len = 100
        encoded = encoded[:max_len]
        encoded_root = encoded_root[:max_len]
        encoded_attr = encoded_attr[:max_len]
        pad = max_len - len(encoded)
        encoded = encoded + [0] * pad
        encoded_root = encoded_root + [0] * pad
        encoded_attr = encoded_attr + [0] * pad

        return (
            torch.tensor(encoded, dtype=torch.long),
            torch.tensor(encoded_root, dtype=torch.long),
            torch.tensor(encoded_attr, dtype=torch.long),
            torch.tensor([mode_idx], dtype=torch.long),
        )


def _read_exact(stream, n: int) -> bytes | None:
    buf = bytearray()
    while len(buf) < n:
        chunk = stream.read(n - len(buf))
        if not chunk:
            return None
        buf.extend(chunk)
    return bytes(buf)


def main() -> int:
    import numpy as np

    try:
        engine = Engine()
        warm = np.zeros(RESAMPLE_RATE * 3, dtype=np.float32)
        engine.predict_pcm(warm, RESAMPLE_RATE)
    except Exception as exc:
        sys.stdout.write(json.dumps({"error": f"model_load_failed: {exc}"}) + "\n")
        sys.stdout.flush()
        return 1

    sys.stdout.write("READY v2\n")
    sys.stdout.flush()

    stream = sys.stdin.buffer
    while True:
        header = _read_exact(stream, HEADER.size)
        if header is None:
            break
        sr, frame_count = HEADER.unpack(header)
        if frame_count == EXIT_FRAME_COUNT:
            break
        payload = _read_exact(stream, frame_count * 4)
        if payload is None:
            break
        try:
            pcm = np.frombuffer(payload, dtype=np.float32)
            out = engine.predict_pcm(pcm, sr)
            sys.stdout.write(json.dumps(out) + "\n")
        except Exception as exc:
            sys.stdout.write(json.dumps({"error": str(exc)}) + "\n")
        sys.stdout.flush()

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

关键差异点（对照 repo 版 predict）：
- MERT 特征不再写 npy，直接内存拼接 layer 5/6（索引语义与 `extract_features_from_segment` 完全一致：`stack(hidden_states).squeeze()[1:]` 后取 5、6）
- BTC 模型、chord json、tag_list、HParams 启动时加载一次
- CQT 用 `librosa.cqt` 直接算内存数组（替代 `audio_file_to_features` 的 `librosa.load`），保留 `np.log(np.abs(feature) + 1e-6)` 和 `feature_per_second = inst_len / timestep`
- 和弦归一化逻辑内联（`normalize_chord` 的内存版），.lab/.midi 仍落临时目录（mir_eval/music21 需要文件路径）
- 启动时跑一次 3 秒静音 dummy 推理（触发 CUDA context 初始化），然后才打印 `READY v2`

- [ ] **Step 2: 修改 verify.py 走新协议并报告设备**

`verify.py` 的 client 调用在 Task 3 才升级。本任务只改 verify.py 的输出部分（`main()` 里 `print` 段），新增两行：

```python
    print(f"device   = {out.get('device', 'unknown')}")
    print(f"moods    = {out.get('moods', [])}")
```

（放在原有 `valence`/`arousal` 打印之后。）

- [ ] **Step 3: 端到端冒烟（等 Task 3 完成后跑，此处先记录）**

本步骤在 Task 3 完成后执行：
Run: `music2emo_engine\.venv\Scripts\python.exe music2emo_engine\verify.py`
Expected: `device = cuda`，`predict took` 显著低于改造前（目标 < 2s，首次含模型加载除外），输出 valence/arousal 数值
若 device = cpu：回到 Task 1 Step 4 排查

- [ ] **Step 4: Commit**

```bash
git add music2emo_engine/server.py music2emo_engine/verify.py
git commit -m "feat(engine): server v2 with preloaded models and in-memory GPU inference"
```

---

### Task 3: client v2 — 二进制帧协议 + 版本握手 + restart

**Files:**
- Modify: `core/music2emo_client.py`（整体重写）
- Test: `tests/test_music2emo_client.py`（新建）

**Interfaces:**
- Consumes: Task 2 的 `READY v2` + 二进制帧协议
- Produces（Task 4 依赖）:
  - `Music2EmoClient(venv_python: str, server_script: str, startup_timeout: float = 300.0)`
  - `client.available -> bool`
  - `client.server_version -> str`（握手行原文，如 `"READY v2"`）
  - `client.predict_audio(audio: np.ndarray, sr: int) -> dict`（audio 单/双声道 float32 [-1,1]；返回 `{"valence","arousal","moods","device"}` 或 `{"error"}`）
  - `client.warmup() -> None`（立即启动子进程并等 READY，用于开始检测时预热）
  - `client.restart() -> None`（杀掉子进程，下次 predict 惰性重启）
  - `client.stop() -> None`

- [ ] **Step 1: 写失败测试**

新建 `tests/test_music2emo_client.py`：

```python
import itertools
import json
import struct
from unittest.mock import MagicMock, patch

import numpy as np

from core.music2emo_client import Music2EmoClient


def make_client():
    return Music2EmoClient("fake_python", "fake_server.py")


def make_proc(response: dict, version: str = "READY v2"):
    proc = MagicMock()
    proc.poll.return_value = None
    replies = itertools.cycle([version + "\n", json.dumps(response) + "\n"])
    proc.stdout.readline.side_effect = lambda: next(replies)

    written = bytearray()

    class Stdin:
        def write(self, data):
            written.extend(data)

        def flush(self):
            pass

    proc.stdin = Stdin()
    return proc, written


def test_predict_audio_sends_binary_frame_and_parses_response():
    response = {"valence": 6.5, "arousal": 3.0, "moods": ["happy"], "device": "cuda"}
    proc, written = make_proc(response)
    client = make_client()

    with patch("subprocess.Popen", return_value=proc):
        audio = np.ones((2, 4800), dtype=np.float32) * 0.5
        out = client.predict_audio(audio, 48000)

    assert client.server_version == "READY v2"
    header = struct.unpack("<II", bytes(written[:8]))
    assert header == (48000, 4800)
    pcm = np.frombuffer(bytes(written[8:]), dtype=np.float32)
    assert pcm.shape == (4800,)
    np.testing.assert_allclose(pcm, 0.5, rtol=1e-6)
    assert out["valence"] == 6.5
    assert out["device"] == "cuda"


def test_predict_audio_converts_stereo_to_mono():
    response = {"valence": 5.0, "arousal": 5.0}
    proc, written = make_proc(response)
    client = make_client()

    audio = np.zeros((2, 100), dtype=np.float32)
    audio[0, :] = 1.0
    audio[1, :] = -1.0

    with patch("subprocess.Popen", return_value=proc):
        client.predict_audio(audio, 48000)

    pcm = np.frombuffer(bytes(written[8:]), dtype=np.float32)
    np.testing.assert_allclose(pcm, 0.0, atol=1e-6)


def test_restart_kills_process_and_forces_relaunch():
    response = {"valence": 5.0, "arousal": 5.0}
    proc, _ = make_proc(response)
    client = make_client()

    with patch("subprocess.Popen", return_value=proc) as popen:
        client.predict_audio(np.zeros(100, dtype=np.float32), 48000)
        assert popen.call_count == 1
        client.restart()
        proc.poll.return_value = 0
        client.predict_audio(np.zeros(100, dtype=np.float32), 48000)
        assert popen.call_count == 2
```

- [ ] **Step 2: 跑测试确认失败**

Run: `C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_music2emo_client.py -v`
Expected: FAIL（`server_version` 属性不存在等）

- [ ] **Step 3: 重写 client**

完整替换 `core/music2emo_client.py`（Popen 用二进制流，readline 兼容 bytes/str 以便 mock）：

```python
"""Client for the isolated music2emo inference server (protocol v2).

The host app talks to the engine subprocess with binary PCM frames on stdin
and JSON lines on stdout, keeping torch/MERT isolated in their own venv.
"""

import json
import os
import struct
import subprocess
import time

import numpy as np

EXIT_FRAME_COUNT = 0xFFFFFFFF
HEADER = struct.Struct("<II")


class Music2EmoClient:
    """Manages a long-lived music2emo server subprocess."""

    def __init__(self, venv_python: str, server_script: str,
                 startup_timeout: float = 300.0):
        self._python = venv_python
        self._script = server_script
        self._startup_timeout = startup_timeout
        self._proc: subprocess.Popen | None = None
        self.server_version: str = ""

    @property
    def available(self) -> bool:
        return bool(self._python and self._script
                    and os.path.isfile(self._python)
                    and os.path.isfile(self._script))

    @staticmethod
    def _readline_text(proc: subprocess.Popen) -> str:
        line = proc.stdout.readline()
        if not line:
            return ""
        if isinstance(line, bytes):
            return line.decode("utf-8", errors="replace")
        return line

    def _ensure_running(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            return
        self._proc = subprocess.Popen(
            [self._python, self._script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=os.path.dirname(self._script),
        )
        deadline = time.time() + self._startup_timeout
        while time.time() < deadline:
            line = self._readline_text(self._proc).strip()
            if not line:
                self._kill()
                raise RuntimeError("music2emo server exited during startup")
            if line.startswith("READY"):
                self.server_version = line
                return
            try:
                payload = json.loads(line)
                if "error" in payload:
                    self._kill()
                    raise RuntimeError(payload["error"])
            except json.JSONDecodeError:
                pass
        self._kill()
        raise TimeoutError("music2emo server startup timed out (model load?)")

    def warmup(self) -> None:
        self._ensure_running()

    def predict_audio(self, audio: np.ndarray, sr: int) -> dict:
        """Send PCM frames to the server. audio: float in [-1,1], mono or 2ch."""
        self._ensure_running()
        assert self._proc is not None and self._proc.stdin is not None

        if audio.ndim == 2:
            mono = audio.mean(axis=0)
        else:
            mono = audio
        pcm = np.ascontiguousarray(mono, dtype=np.float32)

        self._proc.stdin.write(HEADER.pack(sr, pcm.shape[0]))
        self._proc.stdin.write(pcm.tobytes())
        self._proc.stdin.flush()

        line = self._readline_text(self._proc)
        if not line:
            self._kill()
            raise RuntimeError("music2emo server returned nothing")
        return json.loads(line)

    def restart(self) -> None:
        self._kill()

    def stop(self) -> None:
        if self._proc is None:
            return
        try:
            if self._proc.stdin and self._proc.poll() is None:
                self._proc.stdin.write(HEADER.pack(0, EXIT_FRAME_COUNT))
                self._proc.stdin.flush()
                self._proc.wait(timeout=5)
        except Exception:
            pass
        self._kill()

    def _kill(self) -> None:
        if self._proc is None:
            return
        try:
            self._proc.kill()
        except Exception:
            pass
        self._proc = None
```

注意：旧方法 `predict_file` 删除（全项目无调用方，删除前用 `grep -rn "predict_file" --include="*.py"` 确认只剩本文件）。

- [ ] **Step 4: 跑测试确认通过**

Run: `C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_music2emo_client.py -v`
Expected: 3 passed

- [ ] **Step 5: 端到端冒烟（Task 2 Step 3 在此刻执行）**

Run: `music2emo_engine\.venv\Scripts\python.exe music2emo_engine\verify.py`
Expected: `device = cuda`，无 error，预测耗时打印

- [ ] **Step 6: Commit**

```bash
git add core/music2emo_client.py tests/test_music2emo_client.py music2emo_engine/server.py music2emo_engine/verify.py
git commit -m "feat(engine): binary PCM protocol v2 with preloaded GPU inference"
```

---

### Task 4: AudioAnalyzer 重构 — 滑动窗口 + 删除 librosa 回退 + 崩溃重启一次

**Files:**
- Modify: `core/audio_analyzer.py`
- Modify: `gui/main_window.py`（仅 `_start_audio` 预热接线）
- Modify: `tests/test_audio_analyzer_mood_fix.py`（旧文件测的是回退行为，整体替换）
- Delete: 无（librosa 依赖仅从 analyzer 移除，requirements.txt 里 librosa 仍被 spectrum/其他测试引用则保留；确认无引用后从 requirements.txt 删除为可选清理，本任务不做）

**Interfaces:**
- Consumes: Task 3 的 `predict_audio` / `restart` / `available`
- Produces（Task 6 依赖）:
  - `analyzer.set_calibrator(calibrator) -> None`（calibrator 需有 `calibrate(raw_v: float, raw_a: float) -> tuple[float, float]`，输入 1-9 原始分，返回 [-1,1]；本任务内先支持 None）
  - `analyzer.last_raw_va -> tuple[float, float] | None`（最近一次 1-9 原始 (valence, arousal)）
  - 常量 `WINDOW_SECONDS=10.0`、`HOP_SECONDS=2.0`、`MIN_AUDIO_SECONDS=4.0`
  - 信号不变：`mood_analyzed(float,float,str,float)`、`analysis_error(str)`、`boundary_detected()`、`no_audio()`

- [ ] **Step 1: 替换测试文件**

整体替换 `tests/test_audio_analyzer_mood_fix.py`：

```python
import time
from unittest.mock import MagicMock

import numpy as np

from core.audio_analyzer import AudioAnalyzer


def make_analyzer(predict_return=None, side_effect=None, available=True):
    client = MagicMock()
    client.available = available
    client.predict_audio.return_value = predict_return
    client.predict_audio.side_effect = side_effect
    capture = MagicMock()
    capture.sample_rate = 48000
    analyzer = AudioAnalyzer(capture, music2emo_client=client)
    analyzer._signals = MagicMock()
    return analyzer, client


GOOD_RESPONSE = {"valence": 7.0, "arousal": 6.0, "moods": [], "device": "cuda"}


def good_audio(seconds=10.0, sr=48000):
    return np.random.randn(2, int(sr * seconds)).astype(np.float32) * 0.1


def test_analyze_chunk_uses_music2emo_without_fallback():
    analyzer, client = make_analyzer(predict_return=GOOD_RESPONSE)
    result = analyzer._analyze_chunk(good_audio()[0], 48000)
    assert client.predict_audio.called
    assert -1.0 <= result.arousal <= 1.0
    assert -1.0 <= result.valence <= 1.0
    assert result.quadrant in {"VIGOROUS", "TENSE", "MELANCHOLY", "CALM"}


def test_last_raw_va_tracks_server_response():
    analyzer, _ = make_analyzer(predict_return=GOOD_RESPONSE)
    analyzer._analyze_chunk(good_audio()[0], 48000)
    assert analyzer.last_raw_va == (7.0, 6.0)


def test_engine_unavailable_emits_error_no_librosa():
    analyzer, _ = make_analyzer(available=False)
    result = analyzer._analyze_chunk(good_audio()[0], 48000)
    assert result is None
    analyzer._signals.analysis_error.emit.assert_called()


def test_engine_error_response_returns_none():
    analyzer, _ = make_analyzer(predict_return={"error": "boom"})
    result = analyzer._analyze_chunk(good_audio()[0], 48000)
    assert result is None


def test_calibrator_applied_when_set():
    analyzer, _ = make_analyzer(predict_return=GOOD_RESPONSE)
    calibrator = MagicMock()
    calibrator.calibrate.return_value = (0.9, -0.9)
    analyzer.set_calibrator(calibrator)
    result = analyzer._analyze_chunk(good_audio()[0], 48000)
    calibrator.calibrate.assert_called_once_with(7.0, 6.0)
    assert abs(result.valence - 0.9) < 0.35
    assert abs(result.arousal - (-0.9)) < 0.35


def test_loop_restarts_engine_once_then_stops():
    analyzer, client = make_analyzer(side_effect=RuntimeError("server dead"))
    capture = analyzer._capture
    capture.get_snapshot.return_value = good_audio()

    analyzer._running = True
    analyzer._analysis_loop()

    assert client.restart.call_count == 1
    analyzer._signals.analysis_error.emit.assert_called()
    assert analyzer._running is False


def test_loop_skips_when_insufficient_audio():
    analyzer, client = make_analyzer(predict_return=GOOD_RESPONSE)
    capture = analyzer._capture

    def short_audio_then_stop(seconds):
        analyzer._running = False
        return good_audio(seconds=2.0)

    capture.get_snapshot.side_effect = short_audio_then_stop
    analyzer._running = True
    analyzer._analysis_loop()

    assert not client.predict_audio.called


def test_sliding_window_requests_window_seconds():
    analyzer, client = make_analyzer(predict_return=GOOD_RESPONSE)
    capture = analyzer._capture
    capture.get_snapshot.return_value = good_audio()

    calls = []
    orig_emit = analyzer._signals.mood_analyzed.emit

    def stop_after_first(*args):
        calls.append(args)
        analyzer._running = False

    analyzer._signals.mood_analyzed.emit = stop_after_first
    analyzer._running = True
    analyzer._analysis_loop()

    capture.get_snapshot.assert_called_with(AudioAnalyzer.WINDOW_SECONDS)
    assert len(calls) == 1
```

- [ ] **Step 2: 跑测试确认失败**

Run: `C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_audio_analyzer_mood_fix.py -v`
Expected: FAIL（`set_calibrator` / `last_raw_va` / `WINDOW_SECONDS` 不存在）

- [ ] **Step 3: 重写 audio_analyzer.py**

完整替换：

```python
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass

import numpy as np
from PySide6.QtCore import QObject, Signal

from core.audio_capture import AudioCaptureManager


@dataclass
class MoodCoordinates:
    arousal: float
    valence: float
    quadrant: str
    confidence: float


class AnalyzerSignals(QObject):
    mood_analyzed = Signal(float, float, str, float)
    analysis_error = Signal(str)
    boundary_detected = Signal()
    no_audio = Signal()


class AudioAnalyzer:
    WINDOW_SECONDS = 10.0
    HOP_SECONDS = 2.0
    MIN_AUDIO_SECONDS = 4.0
    HISTORY_SIZE = 7
    BOUNDARY_THRESHOLD = 0.8
    BOUNDARY_THRESHOLD_LOCKED = 1.0
    STABILIZATION_COUNT = 4
    COORD_HISTORY = 5
    LOCK_CONFIDENCE = 0.6
    SILENCE_RMS_THRESHOLD = 0.003
    FEATURE_EMA_ALPHA = 0.5
    BOUNDARY_COOLDOWN = 2
    QUADRANT_DEADZONE = 0.08

    def __init__(self, capture_manager: AudioCaptureManager,
                 music2emo_client=None):
        self._capture = capture_manager
        self._m2e_client = music2emo_client
        self._calibrator = None
        self._running = False
        self._thread: threading.Thread | None = None
        self._signals = AnalyzerSignals()
        self._recent_quadrants: deque[str] = deque(maxlen=self.HISTORY_SIZE)
        self._recent_coords: deque[tuple[float, float]] = deque(maxlen=self.COORD_HISTORY)
        self._boundary_countdown: int = 0
        self._boundary_cooldown: int = 0
        self._current_confidence: float = 0.0
        self._locked: bool = False
        self._locked_quadrant: str = ""
        self._locked_arousal: float = 0.0
        self._locked_valence: float = 0.0
        self._last_va: tuple[float, float] | None = None
        self._last_quadrant = ""
        self._last_raw_va: tuple[float, float] | None = None
        self._restart_attempted: bool = False

    @property
    def signals(self) -> AnalyzerSignals:
        return self._signals

    @property
    def last_raw_va(self) -> tuple[float, float] | None:
        return self._last_raw_va

    def set_calibrator(self, calibrator) -> None:
        self._calibrator = calibrator

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._reset_state()
        self._thread = threading.Thread(target=self._analysis_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None
        if self._m2e_client is not None:
            self._m2e_client.stop()

    def force_reset(self) -> None:
        self._reset_state()

    def _reset_state(self) -> None:
        self._recent_quadrants.clear()
        self._recent_coords.clear()
        self._boundary_countdown = 0
        self._boundary_cooldown = 0
        self._locked = False
        self._locked_quadrant = ""
        self._last_va = None
        self._last_quadrant = ""
        self._last_raw_va = None
        self._restart_attempted = False

    def _analysis_loop(self) -> None:
        silence_streak = 0
        while self._running:
            cycle_start = time.monotonic()
            try:
                audio = self._capture.get_snapshot(self.WINDOW_SECONDS)
                if audio is None or audio.shape[1] < int(self.MIN_AUDIO_SECONDS * self._capture.sample_rate):
                    self._wait_next_cycle(cycle_start)
                    continue
                mono = np.mean(audio, axis=0).astype(np.float32)
                rms = float(np.sqrt(np.mean(mono ** 2)))
                if rms < self.SILENCE_RMS_THRESHOLD:
                    silence_streak += 1
                    if silence_streak >= 3:
                        self._signals.no_audio.emit()
                    self._wait_next_cycle(cycle_start)
                    continue
                silence_streak = 0
                result = self._analyze_chunk(mono, self._capture.sample_rate)
                if result is not None:
                    self._handle_result(result)
            except Exception as e:
                if not self._try_restart_engine(str(e)):
                    self._running = False
                    return
            self._wait_next_cycle(cycle_start)

    def _wait_next_cycle(self, cycle_start: float) -> None:
        elapsed = time.monotonic() - cycle_start
        remaining = self.HOP_SECONDS - elapsed
        if remaining > 0:
            threading.Event().wait(timeout=remaining)

    def _try_restart_engine(self, error: str) -> bool:
        if self._restart_attempted or self._m2e_client is None:
            self._signals.analysis_error.emit(f"情绪引擎已停止: {error}")
            return False
        self._restart_attempted = True
        try:
            self._m2e_client.restart()
            return True
        except Exception as exc:
            self._signals.analysis_error.emit(f"情绪引擎已停止: {exc}")
            return False

    def _handle_result(self, result: MoodCoordinates) -> None:
        coord = (result.arousal, result.valence)

        if self._detect_boundary(coord, result):
            self._recent_quadrants.clear()
            self._recent_coords.clear()
            self._boundary_countdown = self.STABILIZATION_COUNT
            self._boundary_cooldown = self.BOUNDARY_COOLDOWN
            self._locked = False
            self._locked_quadrant = ""
            self._signals.boundary_detected.emit()

        self._recent_coords.append(coord)
        self._recent_quadrants.append(result.quadrant)

        if self._locked:
            self._signals.mood_analyzed.emit(
                self._locked_arousal, self._locked_valence,
                self._locked_quadrant, 1.0
            )
            return

        if self._boundary_countdown > 0:
            self._boundary_countdown -= 1
            result.confidence = 0.0
        else:
            result.confidence = self._compute_confidence(result)

        self._current_confidence = result.confidence

        if result.confidence >= self.LOCK_CONFIDENCE:
            self._locked = True
            self._locked_quadrant = result.quadrant
            self._locked_arousal = result.arousal
            self._locked_valence = result.valence

        self._signals.mood_analyzed.emit(
            result.arousal, result.valence,
            result.quadrant, result.confidence
        )

    def _detect_boundary(self, current: tuple[float, float],
                         result: MoodCoordinates) -> bool:
        if self._boundary_cooldown > 0:
            self._boundary_cooldown -= 1
            return False

        if self._locked and result.quadrant != self._locked_quadrant:
            return True

        if len(self._recent_coords) < 3:
            return False

        coords = list(self._recent_coords)
        mean_arousal = sum(c[0] for c in coords) / len(coords)
        mean_valence = sum(c[1] for c in coords) / len(coords)

        da = current[0] - mean_arousal
        dv = current[1] - mean_valence
        distance = (da * da + dv * dv) ** 0.5

        threshold = self.BOUNDARY_THRESHOLD_LOCKED if self._locked else self.BOUNDARY_THRESHOLD
        return distance > threshold

    def _analyze_chunk(self, audio: np.ndarray, sr: int) -> MoodCoordinates | None:
        if self._m2e_client is None or not self._m2e_client.available:
            self._signals.analysis_error.emit("情绪引擎不可用，请检查 music2emo 安装")
            return None
        try:
            out = self._m2e_client.predict_audio(audio, sr)
        except Exception as exc:
            raise RuntimeError(f"music2emo predict failed: {exc}") from exc
        if not isinstance(out, dict) or "error" in out:
            self._signals.analysis_error.emit(
                f"music2emo error: {out.get('error') if isinstance(out, dict) else out}")
            return None
        try:
            raw_arousal = float(out["arousal"])
            raw_valence = float(out["valence"])
            if not np.isfinite(raw_arousal) or not np.isfinite(raw_valence):
                raise ValueError("valence/arousal is not finite")
        except (KeyError, TypeError, ValueError) as exc:
            self._signals.analysis_error.emit(f"music2emo returned invalid scores: {exc}")
            return None

        self._last_raw_va = (raw_valence, raw_arousal)

        if self._calibrator is not None:
            valence, arousal = self._calibrator.calibrate(raw_valence, raw_arousal)
        else:
            arousal = self._normalize_model_score(raw_arousal)
            valence = self._normalize_model_score(raw_valence)

        arousal, valence = self._smooth_va(arousal, valence)
        arousal = max(-1.0, min(1.0, arousal))
        valence = max(-1.0, min(1.0, valence))
        quadrant = self._quadrant_from_va(arousal, valence)
        return MoodCoordinates(arousal, valence, quadrant, 0.0)

    @staticmethod
    def _normalize_model_score(score: float) -> float:
        score = max(1.0, min(9.0, score))
        return (score - 5.0) / 4.0

    def _smooth_va(self, arousal: float, valence: float) -> tuple[float, float]:
        if self._last_va is None:
            self._last_va = (arousal, valence)
            return arousal, valence
        alpha = self.FEATURE_EMA_ALPHA
        a = alpha * arousal + (1 - alpha) * self._last_va[0]
        v = alpha * valence + (1 - alpha) * self._last_va[1]
        self._last_va = (a, v)
        return a, v

    def _quadrant_from_va(self, arousal: float, valence: float) -> str:
        if arousal >= 0 and valence >= 0:
            quadrant = "VIGOROUS"
        elif arousal >= 0 and valence < 0:
            quadrant = "TENSE"
        elif arousal < 0 and valence < 0:
            quadrant = "MELANCHOLY"
        else:
            quadrant = "CALM"

        if self._last_quadrant and quadrant != self._last_quadrant:
            last_arousal_positive = self._last_quadrant in {"VIGOROUS", "TENSE"}
            last_valence_positive = self._last_quadrant in {"VIGOROUS", "CALM"}
            arousal_changed = (arousal >= 0) != last_arousal_positive
            valence_changed = (valence >= 0) != last_valence_positive

            if arousal_changed and not valence_changed:
                if abs(arousal) < self.QUADRANT_DEADZONE:
                    return self._last_quadrant
            elif valence_changed and not arousal_changed:
                if abs(valence) < self.QUADRANT_DEADZONE:
                    return self._last_quadrant

        self._last_quadrant = quadrant
        return quadrant

    def _compute_confidence(self, current: MoodCoordinates) -> float:
        if not self._recent_quadrants:
            return 0.0

        quadrants = list(self._recent_quadrants)
        weights = list(range(1, len(quadrants) + 1))
        total_weight = sum(weights)

        weighted_counts: dict[str, float] = {}
        for q, w in zip(quadrants, weights):
            weighted_counts[q] = weighted_counts.get(q, 0.0) + w

        current_quadrant = current.quadrant
        dominant_quadrant = max(weighted_counts, key=weighted_counts.get)

        if current_quadrant != dominant_quadrant:
            return 0.0

        consistency = weighted_counts[dominant_quadrant] / total_weight
        margin = min(abs(current.arousal), abs(current.valence))
        margin_factor = min(margin / 0.4, 1.0)

        return consistency * 0.6 + margin_factor * 0.4
```

设计取舍说明：spec 提到「推理异步非阻塞（投递+收结果）」。实现采用分析线程内阻塞调用——GPU 推理已降至亚秒级（占 2s 步进的 <25%），专用队列属过度设计（YAGNI）；`_wait_next_cycle` 用单调时钟对齐节奏，慢于 2s 的推理自然跳拍不堆积。librosa 导入与 `_extract_features`/`_map_to_quadrant`/NORM_* 常量全部删除。

- [ ] **Step 4: main_window 启动时预热引擎子进程**

`gui/main_window.py` 的 `_start_audio` 改为：

```python
    def _start_audio(self):
        if self._audio_capture.start():
            if self._m2e_client is not None:
                try:
                    self._m2e_client.warmup()
                except Exception as e:
                    self._signals.error_occurred.emit(f"情绪引擎启动失败: {e}")
                    return
            self._audio_analyzer.start()
            self._mood_active = True
        else:
            print("[AUDIO] 音频捕获启动失败", file=sys.stderr, flush=True)
            self._signals.error_occurred.emit("音频捕获启动失败，请检查 Apple Music 是否正在播放")
```

这样模型加载/CUDA 初始化发生在按下开始键的瞬间（后台线程内，不卡 UI），第一个 10 秒窗口攒满时即可直接推理。

- [ ] **Step 5: 跑测试确认通过**

Run: `C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_audio_analyzer_mood_fix.py -v`
Expected: 8 passed

- [ ] **Step 6: 全量测试确认无回归**

Run: `C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/ -v`
Expected: 全绿（注意 `tests/` 里旧版 test_audio_analyzer.py 已被用户删除，若仍存在且失败则一并删除它）

- [ ] **Step 7: Commit**

```bash
git add core/audio_analyzer.py tests/test_audio_analyzer_mood_fix.py gui/main_window.py
git commit -m "feat(analyzer): 10s/2s sliding window, drop librosa fallback, restart engine once"
```

---

### Task 5: 个性化校准模块 core/mood_calibration.py

**Files:**
- Create: `core/mood_calibration.py`
- Test: `tests/test_mood_calibration.py`（新建）

**Interfaces:**
- Consumes: 无
- Produces（Task 6 依赖）:
  - `CalibrationSample(raw_valence: float, raw_arousal: float, user_valence: float, user_arousal: float, timestamp: float)` dataclass
  - `CalibrationStore(path: str)`：`.samples -> list[CalibrationSample]`、`.add(sample) -> None`（自动持久化）、`.load()`、`.save()`
  - `Calibrator(store: CalibrationStore)`：`.active -> bool`、`.refit() -> None`、`.calibrate(raw_v, raw_a) -> tuple[float, float]`、`.MIN_SAMPLES = 10`

- [ ] **Step 1: 写失败测试**

```python
import numpy as np

from core.mood_calibration import Calibrator, CalibrationSample, CalibrationStore


def make_samples(n, raw_offset=0.0):
    return [
        CalibrationSample(
            raw_valence=1.0 + 8.0 * i / max(n - 1, 1),
            raw_arousal=1.0 + 8.0 * i / max(n - 1, 1),
            user_valence=-0.8 + 1.6 * i / max(n - 1, 1) + raw_offset,
            user_arousal=-0.8 + 1.6 * i / max(n - 1, 1),
            timestamp=1000.0 + i,
        )
        for i in range(n)
    ]


def test_store_persists_and_loads(tmp_path):
    path = str(tmp_path / "cal.json")
    store = CalibrationStore(path)
    store.add(make_samples(1)[0])
    reloaded = CalibrationStore(path)
    assert len(reloaded.samples) == 1
    assert reloaded.samples[0].raw_valence == 1.0


def test_store_handles_missing_file(tmp_path):
    store = CalibrationStore(str(tmp_path / "nope.json"))
    assert store.samples == []


def test_calibrator_identity_below_min_samples(tmp_path):
    store = CalibrationStore(str(tmp_path / "cal.json"))
    for s in make_samples(5):
        store.add(s)
    cal = Calibrator(store)
    assert cal.active is False
    v, a = cal.calibrate(7.0, 3.0)
    assert v == (7.0 - 5.0) / 4.0
    assert a == (3.0 - 5.0) / 4.0


def test_calibrator_fits_isotonic_at_min_samples(tmp_path):
    store = CalibrationStore(str(tmp_path / "cal.json"))
    for s in make_samples(12):
        store.add(s)
    cal = Calibrator(store)
    assert cal.active is True
    v, a = cal.calibrate(9.0, 9.0)
    assert v > 0.6
    assert a > 0.6
    v_low, _ = cal.calibrate(1.0, 1.0)
    assert v_low < -0.6


def test_calibrator_clips_out_of_bounds(tmp_path):
    store = CalibrationStore(str(tmp_path / "cal.json"))
    for s in make_samples(12):
        store.add(s)
    cal = Calibrator(store)
    v, a = cal.calibrate(99.0, -5.0)
    assert -1.0 <= v <= 1.0
    assert -1.0 <= a <= 1.0


def test_refit_after_adding_samples(tmp_path):
    store = CalibrationStore(str(tmp_path / "cal.json"))
    cal = Calibrator(store)
    assert cal.active is False
    for s in make_samples(12):
        store.add(s)
    cal.refit()
    assert cal.active is True
```

- [ ] **Step 2: 跑测试确认失败**

Run: `C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_mood_calibration.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 core/mood_calibration.py**

```python
"""Personalized mood calibration.

Collects (model raw 1-9 score -> user-perceived VA) sample pairs and fits an
isotonic regression per dimension. Below MIN_SAMPLES the mapping falls back
to the default linear normalization (score - 5) / 4.
"""

import json
import os
import time
from dataclasses import asdict, dataclass

import numpy as np
from sklearn.isotonic import IsotonicRegression


@dataclass
class CalibrationSample:
    raw_valence: float
    raw_arousal: float
    user_valence: float
    user_arousal: float
    timestamp: float


class CalibrationStore:
    def __init__(self, path: str):
        self._path = path
        self.samples: list[CalibrationSample] = []
        self.load()

    def load(self) -> None:
        if not os.path.isfile(self._path):
            self.samples = []
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.samples = [CalibrationSample(**item) for item in data]
        except (json.JSONDecodeError, TypeError, KeyError):
            self.samples = []

    def save(self) -> None:
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump([asdict(s) for s in self.samples], f, ensure_ascii=False, indent=2)

    def add(self, sample: CalibrationSample) -> None:
        self.samples.append(sample)
        self.save()


class Calibrator:
    MIN_SAMPLES = 10

    def __init__(self, store: CalibrationStore):
        self._store = store
        self._v_model: IsotonicRegression | None = None
        self._a_model: IsotonicRegression | None = None
        self.refit()

    @property
    def active(self) -> bool:
        return self._v_model is not None and self._a_model is not None

    def refit(self) -> None:
        samples = self._store.samples
        if len(samples) < self.MIN_SAMPLES:
            self._v_model = None
            self._a_model = None
            return
        raw_v = np.array([s.raw_valence for s in samples])
        raw_a = np.array([s.raw_arousal for s in samples])
        user_v = np.array([s.user_valence for s in samples])
        user_a = np.array([s.user_arousal for s in samples])
        self._v_model = IsotonicRegression(out_of_bounds="clip").fit(raw_v, user_v)
        self._a_model = IsotonicRegression(out_of_bounds="clip").fit(raw_a, user_a)

    def calibrate(self, raw_valence: float, raw_arousal: float) -> tuple[float, float]:
        if not self.active:
            return (
                self._default_normalize(raw_valence),
                self._default_normalize(raw_arousal),
            )
        v = float(self._v_model.predict([raw_valence])[0])
        a = float(self._a_model.predict([raw_arousal])[0])
        return (
            max(-1.0, min(1.0, v)),
            max(-1.0, min(1.0, a)),
        )

    @staticmethod
    def _default_normalize(score: float) -> float:
        score = max(1.0, min(9.0, score))
        return (score - 5.0) / 4.0
```

- [ ] **Step 4: 跑测试确认通过**

Run: `C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_mood_calibration.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add core/mood_calibration.py tests/test_mood_calibration.py
git commit -m "feat(calibration): isotonic personal calibration store and calibrator"
```

---

### Task 6: 校正 UI — 象限图 3x3 网格 + 接线

**Files:**
- Create: `gui/calibration_popover.py`
- Modify: `gui/main_window.py`（多处，见下）
- Test: `tests/test_calibration_popover.py`（新建，轻量）

**Interfaces:**
- Consumes: Task 4 的 `analyzer.set_calibrator` / `last_raw_va`；Task 5 的 `CalibrationStore` / `Calibrator` / `CalibrationSample`
- Produces: `CalibrationPopover(parent=None)`，信号 `corrected = Signal(float, float)`（user_valence, user_arousal）；`gui/main_window.py` 中 `_on_correct_mood()` / `_save_correction(raw, v, a)`

- [ ] **Step 1: 写失败测试**

```python
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from gui.calibration_popover import CalibrationPopover


def _app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_popover_emits_correct_cell_coordinates():
    _app()
    pop = CalibrationPopover()
    received = []
    pop.corrected.connect(lambda v, a: received.append((v, a)))
    pop._emit_cell(0, 0)
    assert received == [(-2 / 3, 2 / 3)]
    pop._emit_cell(2, 2)
    assert received[-1] == (2 / 3, -2 / 3)


def test_popover_center_cell_is_zero():
    _app()
    pop = CalibrationPopover()
    received = []
    pop.corrected.connect(lambda v, a: received.append((v, a)))
    pop._emit_cell(1, 1)
    assert received == [(0.0, 0.0)]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_calibration_popover.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 gui/calibration_popover.py**

3x3 网格：行 = arousal（上高下低），列 = valence（左负右正）。单元格中心值取 {-2/3, 0, 2/3}。

```python
"""Calibration popover — 3x3 valence-arousal grid for user correction."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialog, QGridLayout, QPushButton, QVBoxLayout, QLabel

_CELL_VALUE = {-1: -2 / 3, 0: 0.0, 1: 2 / 3}
_ROW_LABELS = ["高能量", "中等", "低能量"]
_COL_LABELS = ["负面", "中性", "愉悦"]


class CalibrationPopover(QDialog):
    corrected = Signal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("校正当前情绪")
        self.setModal(True)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("这首歌实际听起来是什么感觉？"))
        grid = QGridLayout()
        grid.setSpacing(4)
        for row in range(3):
            for col in range(3):
                label = f"{_ROW_LABELS[row]}\n{_COL_LABELS[col]}"
                btn = QPushButton(label)
                btn.setFixedSize(72, 48)
                btn.clicked.connect(
                    lambda checked=False, r=row, c=col: self._emit_cell(r, c))
                grid.addWidget(btn, row, col)
        layout.addLayout(grid)

    def _emit_cell(self, row: int, col: int) -> None:
        arousal = _CELL_VALUE[1 - row]
        valence = _CELL_VALUE[col - 1]
        self.corrected.emit(valence, arousal)
        self.accept()
```

注意 `_emit_cell(row, col)` 的坐标换算：`row 0`（顶行，高能量）→ arousal = +2/3；`col 0`（左列，负面）→ valence = -2/3。信号签名为 `corrected(valence, arousal)`，与 `Calibrator.calibrate` 返回顺序一致。

- [ ] **Step 4: 跑测试确认通过**

Run: `C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_calibration_popover.py -v`
Expected: 2 passed

- [ ] **Step 5: main_window 接线**

`gui/main_window.py` 改动：

(a) 顶部 import 增加：

```python
import time
from PySide6.QtWidgets import QPushButton
from core.mood_calibration import Calibrator, CalibrationSample, CalibrationStore
from gui.calibration_popover import CalibrationPopover
```

(b) `__init__` 中 `self._audio_analyzer = AudioAnalyzer(...)` 之后加：

```python
        self._calibration_store = CalibrationStore("calibration_samples.json")
        self._calibrator = Calibrator(self._calibration_store)
        self._audio_analyzer.set_calibrator(self._calibrator)
```

(c) `_init_ui` 中 `self._quadrant_chart = QuadrantChart(self)` 之后加「校正」小按钮（作为 chart 的子控件，右上角）：

```python
        self._calib_button = QPushButton("校正", self._quadrant_chart)
        self._calib_button.setFixedSize(44, 22)
        self._calib_button.clicked.connect(self._on_correct_mood)
        self._calib_button.hide()
```

在 `showEvent` 里定位并显示：

```python
    def showEvent(self, event):
        super().showEvent(event)
        self._calib_button.move(self._quadrant_chart.width() - 48, 4)
        self._calib_button.show()
```

(d) 新增两个方法：

```python
    def _on_correct_mood(self):
        raw = self._audio_analyzer.last_raw_va
        if raw is None:
            self._signals.error_occurred.emit("还没有分析结果，无法校正")
            return
        pop = CalibrationPopover(self)
        pop.corrected.connect(lambda v, a: self._save_correction(raw, v, a))
        pop.exec()

    def _save_correction(self, raw: tuple[float, float], v: float, a: float):
        self._calibration_store.add(CalibrationSample(
            raw_valence=raw[0], raw_arousal=raw[1],
            user_valence=v, user_arousal=a,
            timestamp=time.time(),
        ))
        self._calibrator.refit()
        n = len(self._calibration_store.samples)
        state = "已生效" if self._calibrator.active else f"{n}/{self._calibrator.MIN_SAMPLES}"
        self._track_card.set_track(f"校正值已记录（{state}）")
```

- [ ] **Step 6: 手动验证（启动 app）**

Run: `C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe main.py`
操作：播放音乐 → 点「校正」→ 选格子 → 确认 `calibration_samples.json` 生成且内容正确
Expected: 累计 10 条后象限点位置开始偏离默认线性映射

- [ ] **Step 7: Commit**

```bash
git add gui/calibration_popover.py gui/main_window.py tests/test_calibration_popover.py
git commit -m "feat(calibration): 3x3 correction grid wired into analyzer pipeline"
```

---

### Task 7: OCR 框选常驻

**Files:**
- Modify: `gui/main_window.py`（`_OcrHighlightOverlay` 类 + `_show_ocr_highlights` + `_on_start_toggle`）

**Interfaces:**
- Consumes: 无（独立任务）
- Produces: `_OcrHighlightOverlay.update_rects(rects: list[tuple[int,int,int,int,str]]) -> None`；overlay 生命周期：停止按钮 / 主窗口关闭时销毁

- [ ] **Step 1: 改 overlay 类**

`_OcrHighlightOverlay` 删除 `_DISPLAY_MS` 常量和 `QTimer.singleShot(...)` 行，新增：

```python
    def update_rects(self, rects: list[tuple[int, int, int, int, str]]) -> None:
        self._rects = rects
        self.update()
```

- [ ] **Step 2: 改 `_show_ocr_highlights` 复用实例**

先删除方法开头的销毁块：

```python
        if self._ocr_overlay_widget is not None:
            self._ocr_overlay_widget.close()
            self._ocr_overlay_widget = None
```

再把方法尾部原来的「总是新建 overlay」两行替换为复用逻辑：

```python
        geo = screen.geometry() if screen else QRect(0, 0, 1920, 1080)
        if self._ocr_overlay_widget is not None:
            self._ocr_overlay_widget.setGeometry(geo)
            self._ocr_overlay_widget.update_rects(rects)
            if not self._ocr_overlay_widget.isVisible():
                self._ocr_overlay_widget.show()
        else:
            self._ocr_overlay_widget = _OcrHighlightOverlay(rects, geo, self)
            self._ocr_overlay_widget.show()
```

- [ ] **Step 3: 停止时销毁**

`_on_start_toggle` 的停止分支（`if self._running:` 块内）加：

```python
            if self._ocr_overlay_widget is not None:
                self._ocr_overlay_widget.close()
                self._ocr_overlay_widget = None
```

- [ ] **Step 4: 手动验证**

Run: `C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe main.py`
操作：启动检测 → 框选出现后不消失；切歌后框选原位更新；点停止后框选消失
Expected: 不再有 1.5s 自动关闭

- [ ] **Step 5: Commit**

```bash
git add gui/main_window.py
git commit -m "feat(ocr): persistent highlight overlay with in-place rect updates"
```

---

### Task 8: MERT-v1-330M 兼容性验证（实验任务）

spec 风险点：现有回归头 `FeedforwardModelMTAttnCK` 输入 1536（95M 的 768×2），330M hidden=1024 → 拼接后 2048，**预期不兼容**。本任务用脚本实测确认并留档，不重训（DEAM 重训需下载数据集，属后续独立计划）。

**Files:**
- Create: `music2emo_engine/verify_330m.py`

**Interfaces:**
- Consumes: Task 2 的 `M2E_MERT_MODEL` 环境变量机制
- Produces: 终端报告：330M embedding 维度 vs 头部输入 1536；结论写入当日 memory

- [ ] **Step 1: 写 verify_330m.py**

```python
"""Check whether MERT-v1-330M embeddings fit the existing regression head.

Run with the engine venv:
    music2emo_engine\\.venv\\Scripts\\python.exe music2emo_engine\\verify_330m.py

Exit 0 if compatible, 1 if not (expected: 330M hidden=1024 -> 2048 != 1536).
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.join(_HERE, "music2emo_repo")
os.chdir(REPO_DIR)
sys.path.insert(0, REPO_DIR)

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ["M2E_MERT_MODEL"] = "m-a-p/MERT-v1-330M"

import numpy as np
import torch
from utils.mert import FeatureExtractorMERT

EXPECTED_DIM = 1536


def main() -> int:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    extractor = FeatureExtractorMERT(
        model_name=os.environ["M2E_MERT_MODEL"], device=device, sr=24000)
    seg = np.random.randn(24000 * 5).astype(np.float32) * 0.05
    inputs = extractor.processor(seg, sampling_rate=24000, return_tensors="pt").to(device)
    with torch.no_grad():
        outputs = extractor.model(**inputs, output_hidden_states=True)
    layers = torch.stack(outputs.hidden_states).squeeze()[1:, :, :].unsqueeze(0)
    feats = layers.mean(dim=2).cpu().numpy()
    concat = np.concatenate([feats[:, 5, :], feats[:, 6, :]], axis=1).squeeze()
    print(f"330M embedding dim (layers 5,6 concat): {concat.shape[0]}")
    print(f"regression head expects: {EXPECTED_DIM}")
    if concat.shape[0] == EXPECTED_DIM:
        print("COMPATIBLE: backbone swap possible without retraining.")
        return 0
    print("INCOMPATIBLE: head retrain on 330M embeddings required (DEAM).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: 运行验证**

Run: `music2emo_engine\.venv\Scripts\python.exe music2emo_engine\verify_330m.py`
Expected: exit 1，打印 `2048 != 1536 INCOMPATIBLE`（首次运行下载 330M 模型约 1.3GB）
若意外 exit 0：回到 spec 第 1.1 节走直接替换路径（改 `M2E_MERT_MODEL` 环境变量即可）

- [ ] **Step 3: 记录结论**

把结果写入当日 `.workbuddy/memory/YYYY-MM-DD.md`：330M 兼容性结论 + 后续 DEAM 重训计划的触发条件（用户愿意下载 DEAM 数据集时启动）。

- [ ] **Step 4: Commit**

```bash
git add music2emo_engine/verify_330m.py
git commit -m "chore(engine): add MERT-v1-330M compatibility check script"
```

---

## 收尾检查（全部任务完成后）

- [ ] `C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/ -v` 全绿
- [ ] `verify.py` 显示 `device = cuda` 且推理 < 2s
- [ ] 手动跑 app：象限 2s 连续更新、校正按钮可用、OCR 框选常驻
- [ ] 边界检测手感实测：切歌后重置是否及时（若太灵敏/太迟钝，微调 `BOUNDARY_THRESHOLD`，属实测调参，单列一次 commit）
