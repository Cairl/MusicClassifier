# 模板匹配与采集向导设计

## 背景

当前 `ActionExecutor.classify_track` 的流程过于简单：点击三点 → OCR 识别"添加到歌单" → OCR 查找目标歌单名。存在以下问题：

1. 不支持两级菜单（卷 → 歌单），无法处理目标歌单在子菜单中的情况
2. 使用 OCR 识别菜单项不够稳定，菜单文字小、对比度低时识别率差
3. 归类完成后没有删除歌曲的步骤
4. 没有视觉参考库，无法验证 OCR 结果

## 目标

- 用 OpenCV 模板匹配（`cv2.matchTemplate`）替代 OCR 处理所有菜单操作
- 实现完整的 6 步归类流程，支持两级菜单导航和归类后删除
- 提供应用内引导式模板采集向导，让用户逐步截取所有必需模板

## 设计

### 1. 模板库（`core/template_library.py`）

#### 存储结构

```
templates/
├── ui/
│   └── add_to_playlist.png
├── volumes/
│   ├── 风之卷.png
│   ├── 花之卷.png
│   ├── 海之卷.png
│   └── 月之卷.png
└── playlists/
    ├── 季风.png
    ├── 飓风.png
    ├── ...
    └── 新月.png
```

模板使用 PNG 无损格式保存，避免 JPEG 压缩伪影影响匹配精度。`templates/` 目录加入 `.gitignore`。

#### 模板命名

使用 `category/name` 格式引用模板：
- `ui/add_to_playlist` — 通用 UI 按钮
- `volumes/风之卷` — 卷名
- `playlists/季风` — 歌单名

#### `TemplateLibrary` 类

```python
@dataclass
class MatchResult:
    position: tuple[int, int]
    confidence: float

class TemplateLibrary:
    def __init__(self, templates_dir: Path, threshold: float = 0.8)

    def find_template(self, screenshot: np.ndarray, name: str) -> MatchResult | None
    def has_template(self, name: str) -> bool
    def save_template(self, name: str, image: np.ndarray) -> None
    def list_templates(self) -> dict[str, list[str]]
    def get_missing_templates(self, config: PlaylistConfig) -> list[str]
    def delete_template(self, name: str) -> None
```

- `find_template`：使用 `cv2.matchTemplate` + `cv2.TM_CCOEFF_NORMED`，在截图中搜索模板。返回匹配区域中心坐标（相对于截图）和置信度，低于阈值返回 `None`。
- `get_missing_templates`：根据 `config.json` 中定义的卷和歌单，计算全部必需模板列表，返回尚未采集的模板名。
- `threshold` 可通过 `config.json` 配置。

### 2. 重构 ActionExecutor

#### 新的 `classify_track` 签名

```python
def classify_track(self, dots_pos: tuple[int, int], playlist_name: str,
                   volume_name: str, track_name: str) -> ClassificationResult
```

新增 `volume_name` 参数。

#### 6 步操作流程

```
Step 1: click_dots_button(dots_pos)
    点击歌曲同行的三点图标
    ↓
Step 2: find_and_click_add_to_playlist()
    截图 → 模板匹配 "ui/add_to_playlist" → 点击
    ↓
Step 3: try_click_playlist(playlist_name)
    截图 → 模板匹配 "playlists/{playlist_name}"
    找到 → 点击 → 跳至 Step 5
    未找到 → 继续 Step 4
    ↓
Step 4: find_and_click_volume_then_playlist(volume_name, playlist_name)
    截图 → 模板匹配 "volumes/{volume_name}" → 点击
    等待子菜单展开
    截图 → 模板匹配 "playlists/{playlist_name}" → 点击
    ↓
Step 5: click_dots_button(dots_pos)
    再次点击三点图标（重新打开上下文菜单）
    ↓
Step 6: press_delete()
    pyautogui.press('delete')
```

#### 每步的通用模式

每步遵循：截图 → 模板匹配 → 坐标转换 → 操作 → 等待。

```python
def _screenshot_and_find(self, template_name: str) -> tuple[int, int] | None:
    screen = self._screen_capture.capture_full_window(delay_ms=self._menu_appear_ms)
    if screen is None:
        return None
    match = self._template_lib.find_template(screen, template_name)
    if match is None:
        return None
    offset = self._screen_capture._window_rect[:2] if self._screen_capture._window_rect else (0, 0)
    return (match.position[0] + offset[0], match.position[1] + offset[1])
```

`find_template` 返回的 `MatchResult.position` 是相对于截图的坐标。`_screenshot_and_find` 加上窗口左上角的屏幕偏移量，返回 `pyautogui.click()` 所需的屏幕绝对坐标。

#### 错误处理

每步失败时返回 `ClassificationResult(success=False, ...)`，message 明确说明失败原因：

| 步骤 | 失败 message |
|------|-------------|
| Step 1 | `"三点按钮点击失败"` |
| Step 2 | `"未找到「添加到播放列表」按钮"` |
| Step 2 | `"模板 templates/ui/add_to_playlist.png 不存在，请先采集"` |
| Step 3+4 | `"未找到歌单「{name}」或卷「{vol}」"` |
| Step 4 | `"模板 templates/volumes/{vol}.png 不存在，请先采集"` |
| Step 5 | `"三点按钮点击失败（删除前）"` |
| Step 6 | `"删除操作失败"` |

#### 废弃的方法

- `click_add_to_playlist` — 被 Step 2 的模板匹配替代
- `click_target_playlist` — 被 Step 3 + Step 4 替代
- ActionExecutor 不再依赖 `OCRReader.read_playlist_names`

#### 保留的依赖

- `OCRReader.read_tracks` — 歌曲列表识别仍用 OCR（动态内容，无法模板匹配）
- `ScreenCapture` — 截图功能不变

### 3. 模板采集向导（`gui/capture_wizard.py`）

#### 入口

主窗口添加 `工具 → 模板采集` 菜单项，打开 `CaptureWizard` 对话框。

#### 采集顺序

共 21 个模板，按以下顺序采集：

1. UI 按钮（1 张）：`ui/add_to_playlist`
2. 卷名（4 张）：`volumes/风之卷` → `volumes/花之卷` → `volumes/海之卷` → `volumes/月之卷`
3. 歌单名（16 张）：按 config.json 中 volumes → moods 的顺序

#### 向导界面

```
┌──────────────────────────────────────────┐
│  模板采集向导                    (3/21)    │
│                                          │
│  当前需要采集:                            │
│  ■ UI 按钮: "添加到播放列表"               │
│                                          │
│  操作说明:                                │
│  1. 在 Apple Music 中右键任意歌曲          │
│  2. 确保菜单中 "添加到播放列表" 可见        │
│  3. 点击下方「截取选区」按钮               │
│                                          │
│  ┌──────────────────────────────┐        │
│  │   [预览区域 - 截取后显示]     │        │
│  └──────────────────────────────┘        │
│                                          │
│  [跳过]  [截取选区]  [确认并重截]          │
│                                          │
│  ━━━━━━━━━━━━━━━━━━━━━━━  14%            │
└──────────────────────────────────────────┘
```

#### 每步的引导文案

| 模板类型 | 引导文案 |
|---------|---------|
| `ui/add_to_playlist` | "请右键 Apple Music 中任意歌曲，展开上下文菜单" |
| `volumes/{name}` | "请右键歌曲 → 添加到播放列表，确保「{name}」可见" |
| `playlists/{name}` | "请展开「{volume}」子菜单，确保「{name}」可见" |

#### 截取交互

用户点击「截取选区」后：

1. 程序调用 `ScreenCapture.capture_full_window()` 截取 Apple Music 全窗口
2. 弹出 `CropDialog`：显示截图，用户用鼠标拖拽框选目标文字区域
3. 裁剪选区并在向导预览区显示
4. 用户点击「确认」→ `TemplateLibrary.save_template()` 保存
5. 用户点击「确认并重截」→ 重新截图
6. 用户点击「跳过」→ 跳过当前模板

#### CropDialog（截图裁剪对话框）

- 显示完整窗口截图，缩放至对话框大小但保持比例
- 鼠标拖拽绘制矩形选区（橡皮筋效果）
- 选区高亮，选区外半透明遮罩
- 「确认」返回裁剪后的 numpy 数组，「取消」返回 None

### 4. 主窗口集成

#### 模板缺失提示

启动时调用 `template_lib.get_missing_templates(config)`：
- 有缺失 → 按钮网格上方显示黄色提示条："缺少 N 个模板，请先进行模板采集"
- 缺失模板对应的歌单按钮禁用

#### 分类按钮参数变更

当前 `_on_classify(playlist_name)` → 新增 `_on_classify(playlist_name, volume_name)`。

按钮网格构建时，每行已知对应的 `volume_name`，通过 `partial` 绑定。

#### config.json 新增字段

```json
{
  "template_matching": {
    "threshold": 0.8,
    "templates_dir": "templates"
  }
}
```

### 5. 文件结构变更

```
MusicClassifier/
├── core/
│   ├── template_library.py    # 新增
│   ├── action_executor.py     # 修改：6 步流程 + 模板匹配
│   ├── models.py              # 新增 MatchResult 数据类
│   └── ...
├── gui/
│   ├── main_window.py         # 修改：模板检查、volume_name 传递、菜单项
│   ├── capture_wizard.py      # 新增：采集向导
│   └── crop_dialog.py         # 新增：截图裁剪对话框
├── templates/                  # 新增（gitignore）
│   ├── ui/
│   ├── volumes/
│   └── playlists/
└── tests/
    ├── test_template_library.py  # 新增
    ├── test_action_executor.py   # 新增
    └── ...（现有测试更新）
```

### 6. 测试

#### `test_template_library.py`

- `test_find_template_returns_position`：mock `cv2.matchTemplate` 返回高置信度结果
- `test_find_template_returns_none_below_threshold`：低置信度时返回 None
- `test_has_template_true_and_false`：检查文件存在性
- `test_save_template_creates_file`：验证文件写入
- `test_get_missing_templates`：传入 mock config，返回缺失列表
- `test_list_templates`：列出已采集的模板分类

#### `test_action_executor.py`

- `test_classify_track_full_flow`：mock 模板库全部匹配成功，验证 6 步操作序列
- `test_classify_track_playlist_in_first_level`：Step 3 匹配成功，跳过 Step 4
- `test_classify_track_playlist_in_volume`：Step 3 失败，Step 4 成功
- `test_classify_track_missing_template`：模板不存在时返回明确错误
- `test_classify_track_add_to_playlist_not_found`：Step 2 匹配失败
- `test_press_delete_called_after_reclassify`：验证 Step 5-6 执行

所有测试 mock `pyautogui`、`ScreenCapture`、`TemplateLibrary`，无需真实窗口或模板图片。

### 7. 不变的部分

- `OCRReader.read_tracks` — 歌曲列表识别逻辑不变
- `ScreenCapture` — 截图功能不变
- `PlaylistConfig` — 配置加载不变（仅新增 `template_matching` 字段的读取）
- `config.json` 中 `volumes`、`action_delays`、`apple_music_window_title` 不变
