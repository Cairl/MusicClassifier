import sys
import traceback
import threading
from functools import partial
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QMessageBox, QFrame,
)
from PySide6.QtCore import Signal, QObject, Qt, QSize
from PySide6.QtGui import QGuiApplication, QIcon, QPixmap, QPainter, QColor, QPen

from core.models import TrackInfo, ClassificationResult
from core.screen_capture import ScreenCapture
from core.ocr_reader import OCRReader
from core.action_executor import ActionExecutor
from core.playlist_config import PlaylistConfig
from core.template_library import TemplateLibrary
from gui.capture_wizard import CaptureWizard
from core.audio_capture import AudioCaptureManager
from core.audio_analyzer import AudioAnalyzer
from gui.quadrant_chart import QuadrantChart
from process_audio_capture import ProcessAudioCapture


def _draw_svg_icon(size: int, color: str, paths: list[str], fill: bool = False) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color))
    pen.setWidth(1.5)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    if fill:
        painter.setBrush(QColor(color))
    else:
        painter.setBrush(Qt.BrushStyle.NoBrush)
    for path_data in paths:
        from PySide6.QtGui import QPainterPath
        path = QPainterPath()
        parts = path_data.split()
        i = 0
        while i < len(parts):
            cmd = parts[i]
            if cmd == 'M':
                path.moveTo(float(parts[i+1]), float(parts[i+2]))
                i += 3
            elif cmd == 'L':
                path.lineTo(float(parts[i+1]), float(parts[i+2]))
                i += 3
            elif cmd == 'C':
                path.cubicTo(float(parts[i+1]), float(parts[i+2]),
                             float(parts[i+3]), float(parts[i+4]),
                             float(parts[i+5]), float(parts[i+6]))
                i += 7
            elif cmd == 'Q':
                path.quadTo(float(parts[i+1]), float(parts[i+2]),
                            float(parts[i+3]), float(parts[i+4]))
                i += 5
            elif cmd == 'A':
                cx, cy, rx, ry, start, sweep = float(parts[i+1]), float(parts[i+2]), float(parts[i+3]), float(parts[i+4]), float(parts[i+5]), float(parts[i+6])
                path.arcTo(cx-rx, cy-ry, rx*2, ry*2, start, sweep)
                i += 7
            elif cmd == 'Z':
                path.closeSubpath()
                i += 1
            else:
                i += 1
        painter.drawPath(path)
    painter.end()
    return QIcon(pixmap)


_PLAY_ICON_PATHS = [
    "M 7 4 L 16 10 L 7 16 Z"
]

_SETTINGS_ICON_PATHS = [
    "M 5 7 L 15 7",
    "M 5 10 L 15 10",
    "M 5 13 L 15 13"
]

_RECORD_ICON_PATHS = [
    "M 5 10 Q 5 4 10 4 Q 15 4 15 10 L 15 12 L 5 12 Z",
    "M 3 12 L 3 14 Q 3 17 6 17 L 8 17 L 8 14",
    "M 17 12 L 17 14 Q 17 17 14 17 L 12 17 L 12 14",
    "M 8 17 L 8 19 L 12 19 L 12 17",
]


def _make_circle_icon(icon_type: str, color: str, parent=None) -> QPushButton:
    btn = QPushButton(parent)
    btn.setFixedSize(32, 32)
    if icon_type == "play":
        icon = _draw_svg_icon(20, color, _PLAY_ICON_PATHS, fill=True)
    elif icon_type == "record":
        icon = _draw_svg_icon(20, color, _RECORD_ICON_PATHS, fill=False)
    else:
        icon = _draw_svg_icon(20, color, _SETTINGS_ICON_PATHS, fill=False)
    btn.setIcon(icon)
    btn.setIconSize(QSize(20, 20))
    btn.setStyleSheet("""
        QPushButton {
            background-color: transparent;
            border: none;
            border-radius: 16px;
            padding: 0px;
        }
        QPushButton:hover {
            background-color: #e8eaed;
        }
        QPushButton:pressed {
            background-color: #dadce0;
        }
    """)
    return btn

LIGHT_FLAT_QSS = """
QMainWindow {
    background: #fafafa;
}
QWidget#outer {
    background: #fafafa;
}
QWidget#sidebar {
    background: #ffffff;
}
QWidget#track_card {
    background: #ffffff;
    border: none;
    border-radius: 12px;
}
QLabel#track_name {
    font-size: 13px;
    font-weight: 500;
    color: #202124;
}
QLabel#track_subtitle {
    font-size: 11px;
    color: #80868b;
}
QLabel#volume_tag {
    font-size: 10px;
    color: #5f6368;
    font-weight: 600;
    letter-spacing: 0.5px;
}
QLabel#tag_header {
    font-size: 9px;
    font-weight: 600;
    color: #5f6368;
    letter-spacing: 1px;
}
QLabel#volume_label {
    font-size: 11px;
    font-weight: 600;
    color: #202124;
}
QPushButton#playlist_btn {
    background-color: #e8eaed;
    color: #202124;
    border: none;
    border-radius: 8px;
    padding: 6px 4px;
    font-size: 11px;
    min-height: 28px;
}
QPushButton#playlist_btn:hover {
    background-color: #dadce0;
}
QPushButton#playlist_btn:pressed {
    background-color: #c4c7c9;
}
QPushButton#playlist_btn:disabled {
    background-color: #f1f3f4;
    color: #9aa0a6;
}

"""

TAG_ORDER = ["VIGOROUS", "TENSE", "MELANCHOLY", "CALM"]
TAG_LABELS = ["活力", "紧张", "忧郁", "平静"]


class Signals(QObject):
    track_detected = Signal(object)
    classification_done = Signal(object)
    error_occurred = Signal(str)
    window_activated = Signal()


class MainWindow(QMainWindow):
    def __init__(self, config: PlaylistConfig):
        super().__init__()
        self._config = config
        self._signals = Signals()
        self._screen_capture = ScreenCapture(config.window_title)
        self._ocr_reader = OCRReader()
        templates_path = Path(config.templates_dir)
        self._template_lib = TemplateLibrary(templates_path, threshold=config.template_threshold)
        self._action_executor = ActionExecutor(
            self._screen_capture,
            self._template_lib,
            after_click_ms=config.after_click_ms,
            menu_appear_ms=config.menu_appear_ms,
        )
        self._current_track: TrackInfo | None = None
        self._running = False
        self._audio_capture = AudioCaptureManager()
        self._audio_analyzer = AudioAnalyzer(self._audio_capture)
        self._recording = False
        self._playlist_buttons: list[QPushButton] = []
        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        self.setWindowTitle("MusicClassifier")
        screen = QGuiApplication.primaryScreen()
        dpr = screen.devicePixelRatio() if screen else 1.0
        self.setFixedWidth(int(240 * dpr))
        self.setStyleSheet(LIGHT_FLAT_QSS)

        outer = QWidget()
        outer.setObjectName("outer")
        self.setCentralWidget(outer)

        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        body_widget = QWidget()
        body_layout = QHBoxLayout(body_widget)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(48)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(8, 8, 8, 8)
        sidebar_layout.setSpacing(4)
        sidebar_layout.setAlignment(Qt.AlignHCenter)

        self._start_btn = _make_circle_icon("play", "#5f6368", self)
        self._start_btn.clicked.connect(self._on_start_toggle)
        sidebar_layout.addWidget(self._start_btn, 0, Qt.AlignHCenter)

        self._record_btn = _make_circle_icon("record", "#5f6368", self)
        self._record_btn.clicked.connect(self._on_record_toggle)
        sidebar_layout.addWidget(self._record_btn, 0, Qt.AlignHCenter)

        sidebar_layout.addStretch()

        self._capture_btn = _make_circle_icon("settings", "#5f6368", self)
        self._capture_btn.clicked.connect(self._on_open_capture_wizard)
        sidebar_layout.addWidget(self._capture_btn, 0, Qt.AlignHCenter)

        body_layout.addWidget(sidebar)

        separator = QFrame()
        separator.setFixedWidth(1)
        separator.setStyleSheet("background-color: #e8eaed;")

        main_area = QWidget()
        main_layout = QVBoxLayout(main_area)
        main_layout.setContentsMargins(8, 6, 8, 6)
        main_layout.setSpacing(4)

        track_card = QWidget()
        track_card.setObjectName("track_card")
        track_card.setFixedHeight(56)
        track_card_layout = QVBoxLayout(track_card)
        track_card_layout.setContentsMargins(10, 4, 10, 4)
        track_card_layout.setSpacing(0)

        self._volume_tag = QLabel("")
        self._volume_tag.setObjectName("volume_tag")
        track_card_layout.addWidget(self._volume_tag)

        self._track_label = QLabel("等待识别...")
        self._track_label.setObjectName("track_name")
        track_card_layout.addWidget(self._track_label)

        self._album_label = QLabel("")
        self._album_label.setObjectName("track_subtitle")
        track_card_layout.addWidget(self._album_label)

        main_layout.addWidget(track_card)

        self._quadrant_chart = QuadrantChart()
        self._quadrant_chart.setVisible(False)
        main_layout.addWidget(self._quadrant_chart)

        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setSpacing(4)
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

        grid.setRowStretch(len(volumes_seen) + 1, 1)

        main_layout.addWidget(grid_widget)
        body_layout.addWidget(separator)
        body_layout.addWidget(main_area)
        outer_layout.addWidget(body_widget)


    def _connect_signals(self):
        self._signals.track_detected.connect(self._handle_track_detected)
        self._signals.classification_done.connect(self._handle_classification_done)
        self._signals.error_occurred.connect(self._handle_error)
        self._signals.window_activated.connect(self._on_window_activated)
        self._audio_analyzer.signals.mood_analyzed.connect(self._handle_mood_analyzed)
        self._audio_analyzer.signals.analysis_error.connect(self._handle_analysis_error)

    def _on_start_toggle(self):
        if self._running:
            self._running = False
            self._start_btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    border: none;
                    border-radius: 16px;
                    padding: 0px;
                }
                QPushButton:hover {
                    background-color: #e8eaed;
                }
                QPushButton:pressed {
                    background-color: #dadce0;
                }
""")
            self._track_label.setText("等待识别...")
            self._album_label.setText("")
            self._volume_tag.setText("")
            self._set_playlist_buttons_active(False)
        else:
            if not self._screen_capture.find_window():
                QMessageBox.warning(self, "错误",
                    "未找到 Apple Music 窗口，请先打开 Apple Music。")
                return
            self._screen_capture.activate_window()
            self._start_btn.setStyleSheet("""
                QPushButton {
                    background-color: #e8eaed;
                    border: none;
                    border-radius: 16px;
                    padding: 0px;
                }
                QPushButton:hover {
                    background-color: #dadce0;
                }
                QPushButton:pressed {
                    background-color: #c4c7c9;
                }
""")
            self._running = True
            self._capture_and_detect()

    def _set_playlist_buttons_active(self, active: bool):
        for btn in self._playlist_buttons:
            btn.setEnabled(active)
            btn.setProperty("active", "true" if active else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _on_window_activated(self):
        if not self._running:
            return
        image = self._screen_capture.capture_list_region(
            delay_ms=self._config.before_screenshot_ms
        )
        if image is None:
            self._signals.error_occurred.emit(
                "截图失败，请确认 Apple Music 窗口可见")
            return
        offset = (
            self._screen_capture._window_rect[:2]
            if self._screen_capture._window_rect
            else (0, 0)
        )
        tracks = self._ocr_reader.read_tracks(image, offset)
        if not tracks:
            self._signals.error_occurred.emit(
                "OCR 未识别到歌曲，请确认播放列表可见")
            return
        self._signals.track_detected.emit(tracks[0])

    def _capture_and_detect(self):
        if not self._running:
            return

        def worker():
            try:
                activated = self._screen_capture.activate_window()
                if not activated:
                    self._signals.error_occurred.emit(
                        "窗口激活失败，请确认 Apple Music 窗口存在")
                    return
                self._signals.window_activated.emit()
            except Exception as e:
                traceback.print_exc()
                self._signals.error_occurred.emit(f"识别异常: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def _handle_track_detected(self, track: TrackInfo):
        self._current_track = track
        self._track_label.setText(track.display_text())
        self._album_label.setText(
            f"专辑: {track.album}" if track.album else "")
        self._volume_tag.setText("")
        self._set_playlist_buttons_active(True)

        missing = self._template_lib.get_missing_templates(self._config)
        missing_playlists = {
            name.split("/", 1)[1]
            for name in missing if name.startswith("playlists/")
        }

        moods = self._config.get_all_moods_flat()
        volumes_seen: list[str] = []
        for mood in moods:
            vol = mood["volume"]
            if vol not in volumes_seen:
                volumes_seen.append(vol)

        btn_idx = 0
        for volume_name in volumes_seen:
            vol_moods = {m["tag"]: m for m in moods if m["volume"] == volume_name}
            for tag in TAG_ORDER:
                if tag in vol_moods:
                    if btn_idx < len(self._playlist_buttons):
                        if vol_moods[tag]["playlist"] in missing_playlists:
                            self._playlist_buttons[btn_idx].setEnabled(False)
                    btn_idx += 1

    def _on_classify(self, playlist_name: str, volume_name: str):
        if not self._running or not self._current_track:
            return
        track = self._current_track
        self._volume_tag.setText(f"分类至 {volume_name}")
        self._set_playlist_buttons_active(False)

        def worker():
            try:
                result = self._action_executor.classify_track(
                    track.dots_btn_pos, playlist_name, volume_name, track.song_name
                )
                self._signals.classification_done.emit(result)
            except Exception as e:
                traceback.print_exc()
                self._signals.error_occurred.emit(f"分类失败: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def _handle_classification_done(self, result: ClassificationResult):
        if not self._running:
            return
        if result.success:
            self._capture_and_detect()
        else:
            self._signals.error_occurred.emit(result.message)

    def _on_open_capture_wizard(self):
        if not self._screen_capture.find_window():
            QMessageBox.warning(self, "错误",
                "未找到 Apple Music 窗口，请先打开 Apple Music。")
            return
        wizard = CaptureWizard(
            self._screen_capture,
            self._template_lib,
            self._config,
            self,
        )
        wizard.exec()

    def _handle_error(self, msg: str):
        print(f"[ERROR] {msg}", file=sys.stderr, flush=True)
        self._track_label.setText(f"错误: {msg}")
        self._running = False
        self._start_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 16px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #e8eaed;
            }
            QPushButton:pressed {
                background-color: #dadce0;
            }
""")
        self._set_playlist_buttons_active(False)

    def _on_record_toggle(self):
        if self._recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        if not ProcessAudioCapture.is_supported():
            QMessageBox.warning(self, "不支持",
                "当前 Windows 版本不支持进程音频捕获，需要 Windows 10 2004+ 或 Windows 11。")
            return

        self._record_btn.setStyleSheet("""
            QPushButton {
                background-color: #e8eaed;
                border: none;
                border-radius: 16px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #dadce0;
            }
            QPushButton:pressed {
                background-color: #c4c7c9;
            }
        """)

        def worker():
            success = self._audio_capture.start()
            if success:
                self._audio_analyzer.start()
            else:
                self._signals.error_occurred.emit("未找到正在播放音频的 Apple Music 进程")

        self._recording = True
        self._quadrant_chart.setVisible(True)
        self._quadrant_chart.reset()
        threading.Thread(target=worker, daemon=True).start()

    def _stop_recording(self):
        self._recording = False
        self._audio_analyzer.stop()
        self._audio_capture.stop()
        self._quadrant_chart.setVisible(False)
        self._clear_quadrant_highlight()
        self._record_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 16px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #e8eaed;
            }
            QPushButton:pressed {
                background-color: #dadce0;
            }
        """)

    def _handle_mood_analyzed(self, arousal, valence, quadrant, confidence):
        self._quadrant_chart.update_mood(arousal, valence, quadrant, confidence)
        if confidence >= 0.6:
            self._highlight_recommended_quadrant(quadrant)
        else:
            self._clear_quadrant_highlight()

    def _handle_analysis_error(self, msg):
        print(f"[ANALYSIS ERROR] {msg}", file=sys.stderr, flush=True)

    def _highlight_recommended_quadrant(self, quadrant: str):
        tag_col = {"VIGOROUS": 1, "TENSE": 2, "MELANCHOLY": 3, "CALM": 4}
        col = tag_col.get(quadrant)
        if col is None:
            return

        moods = self._config.get_all_moods_flat()
        volumes_seen: list[str] = []
        for mood in moods:
            vol = mood["volume"]
            if vol not in volumes_seen:
                volumes_seen.append(vol)

        btn_idx = 0
        for volume_name in volumes_seen:
            vol_moods = {m["tag"]: m for m in moods if m["volume"] == volume_name}
            for tag in TAG_ORDER:
                if tag in vol_moods:
                    if btn_idx < len(self._playlist_buttons):
                        btn = self._playlist_buttons[btn_idx]
                        if tag == quadrant:
                            btn.setStyleSheet("""
                                QPushButton {
                                    background-color: #e8f0fe;
                                    color: #1a73e8;
                                    border: 2px solid #1a73e8;
                                    border-radius: 8px;
                                    padding: 6px 4px;
                                    font-size: 11px;
                                    min-height: 28px;
                                    font-weight: 600;
                                }
                                QPushButton:hover {
                                    background-color: #d2e3fc;
                                }
                                QPushButton:pressed {
                                    background-color: #aecbfa;
                                }
                            """)
                        else:
                            btn.setStyleSheet("")
                    btn_idx += 1

    def _clear_quadrant_highlight(self):
        for btn in self._playlist_buttons:
            btn.setStyleSheet("")
