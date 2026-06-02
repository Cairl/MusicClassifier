import sys
import traceback
import threading
import ctypes
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QFrame,
)
from PySide6.QtCore import Signal, QObject, Qt, QTimer
from PySide6.QtGui import QGuiApplication, QIcon

from core.models import TrackInfo, ClassificationResult
from core.screen_capture import ScreenCapture
from core.ocr_reader import OCRReader
from core.action_executor import ActionExecutor
from core.playlist_config import PlaylistConfig
from core.template_library import TemplateLibrary
from core.audio_capture import AudioCaptureManager
from core.audio_analyzer import AudioAnalyzer
from process_audio_capture import ProcessAudioCapture

from gui.theme import MAIN_QSS, MOOD_LABELS, MOOD_COLORS
from gui.sidebar import Sidebar
from gui.track_card import TrackCard
from gui.playlist_grid import PlaylistGrid
from gui.quadrant_chart import QuadrantChart
from gui.screenshot_library import ScreenshotLibrary


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

        # ── Services ────────────────────────────────────────────────
        self._screen_capture = ScreenCapture(config.window_title)
        self._ocr_reader = OCRReader()
        templates_path = Path(config.templates_dir)
        self._template_lib = TemplateLibrary(templates_path,
                                             threshold=config.template_threshold)
        self._action_executor = ActionExecutor(
            self._screen_capture, self._template_lib,
            after_click_ms=config.after_click_ms,
            menu_appear_ms=config.menu_appear_ms,
        )
        self._audio_capture = AudioCaptureManager()
        self._audio_analyzer = AudioAnalyzer(self._audio_capture)

        # ── State ───────────────────────────────────────────────────
        self._current_track: TrackInfo | None = None
        self._running = False
        self._mood_active = False
        self._mood_unsupported = not ProcessAudioCapture.is_supported()

        self.setWindowIcon(QIcon())

        # ── Build UI ────────────────────────────────────────────────
        self._init_ui()
        self._connect_signals()

    # ───────────────────────── UI ───────────────────────────────────

    def _init_ui(self):
        self.setWindowTitle("MusicClassifier")
        screen = QGuiApplication.primaryScreen()
        dpr = screen.devicePixelRatio() if screen else 1.0
        self.setFixedWidth(int(240 * dpr))
        self.setFixedHeight(int(360 * dpr))
        self.setStyleSheet(MAIN_QSS)

        outer = QWidget()
        outer.setObjectName("outer")
        self.setCentralWidget(outer)
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        # ── Sidebar ─────────────────────────────────────────────────
        moods = self._config.get_all_moods_flat()
        self._volumes = []
        for mood in moods:
            if mood["volume"] not in self._volumes:
                self._volumes.append(mood["volume"])

        sidebar = Sidebar(self)
        sidebar.play_toggled.connect(self._on_start_toggle)
        sidebar.screenshot_library_requested.connect(self._on_open_screenshot_library)
        self._sidebar = sidebar

        body_layout.addWidget(sidebar)
        body_layout.addWidget(QFrame(
            self, fixedWidth=1,
            styleSheet="background-color: #e8eaed;",
        ))

        # ── Main area ───────────────────────────────────────────────
        main_area = QWidget()
        main_layout = QVBoxLayout(main_area)
        main_layout.setContentsMargins(8, 6, 8, 6)
        main_layout.setSpacing(4)

        self._track_card = TrackCard(self)
        main_layout.addWidget(self._track_card)

        # Mood status bar — idle until user clicks start
        init_text = "点击 ▶ 开始" if not self._mood_unsupported else "环境音频捕获不可用"
        init_style = ("font-size: 10px; font-weight: 400; color: #9aa0a6; "
                      "padding: 3px 8px; border-radius: 6px; background-color: #f1f3f4;")
        self._mood_status = QLabel(init_text)
        self._mood_status.setObjectName("mood_status")
        self._mood_status.setStyleSheet(init_style)
        main_layout.addWidget(self._mood_status)

        self._quadrant_chart = QuadrantChart(self)
        main_layout.addWidget(self._quadrant_chart, 1)

        self._playlist_grid = PlaylistGrid(
            moods, self._volumes, self._on_classify, self,
        )
        main_layout.addWidget(self._playlist_grid)

        body_layout.addWidget(main_area)
        outer_layout.addWidget(body)

    def _connect_signals(self):
        self._signals.track_detected.connect(self._handle_track_detected)
        self._signals.classification_done.connect(self._handle_classification_done)
        self._signals.error_occurred.connect(self._handle_error)
        self._signals.window_activated.connect(self._on_window_activated)
        self._audio_analyzer.signals.mood_analyzed.connect(self._handle_mood_analyzed)
        self._audio_analyzer.signals.analysis_error.connect(self._handle_analysis_error)
        self._audio_analyzer.signals.boundary_detected.connect(self._handle_boundary)
        self._audio_analyzer.signals.no_audio.connect(self._handle_no_audio)

    def showEvent(self, event):
        super().showEvent(event)
        # Nothing starts automatically — user clicks ▶ to begin

    # ───────────────────── Status helper ────────────────────────────

    def _set_status(self, text: str, color: str, bg: str, weight: int = 500):
        self._mood_status.setText(text)
        self._mood_status.setStyleSheet(
            f"font-size: 10px; font-weight: {weight}; color: {color}; "
            f"padding: 3px 8px; border-radius: 6px; background-color: {bg};"
        )

    # ───────────────────── Workflow ─────────────────────────────────

    def _on_start_toggle(self):
        import sys
        if self._running:
            # Stop everything
            self._running = False
            self._mood_active = False
            self._audio_analyzer.stop()
            self._audio_capture.stop()
            self._sidebar.play_button.set_active(False)
            self._track_card.reset()
            self._playlist_grid.set_buttons_active(False)
            self._quadrant_chart.reset()
            self._set_status("已暂停 点击 ▶ 继续", "#9aa0a6", "#f1f3f4", 400)
        else:
            # Start OCR + audio
            if not self._screen_capture.find_window():
                print("[ERROR] 未找到 Apple Music 窗口，请先打开 Apple Music。",
                      file=sys.stderr, flush=True)
                return
            self._screen_capture.activate_window()
            self._sidebar.play_button.set_active(True)
            self._running = True
            self._set_status("启动中...", "#5f6368", "#e8eaed")
            self._capture_and_detect()
            # Start audio detection
            if not self._mood_unsupported:
                threading.Thread(target=self._start_audio, daemon=True).start()

    def _start_audio(self):
        """Background: start audio capture + analysis."""
        if self._audio_capture.start():
            self._audio_analyzer.start()
            self._mood_active = True

    def _on_window_activated(self):
        if not self._running:
            return
        image = self._screen_capture.capture_list_region(
            delay_ms=self._config.before_screenshot_ms
        )
        if image is None:
            self._signals.error_occurred.emit("截图失败，请确认 Apple Music 窗口可见")
            return
        offset = (self._screen_capture._window_rect[:2]
                  if self._screen_capture._window_rect else (0, 0))
        # Get window size for list-region coordinate conversion
        win_w = self._screen_capture._window_rect[2] - self._screen_capture._window_rect[0] \
            if self._screen_capture._window_rect else 0
        win_h = self._screen_capture._window_rect[3] - self._screen_capture._window_rect[1] \
            if self._screen_capture._window_rect else 0

        # Use position templates if available for precise OCR
        # Coordinates are window-relative; need to convert to list-region-relative
        rl, rt, _, _ = self._screen_capture._list_region_ratio

        song_box = self._template_lib.get_cached_region("position/song_name")
        artist_box = self._template_lib.get_cached_region("position/artist")
        tracks = self._ocr_reader.read_tracks(
            image, offset,
            song_region_box=(
                (song_box["x"] - int(win_w * rl),
                 song_box["y"] - int(win_h * rt),
                 song_box["w"], song_box["h"])
            ) if song_box and win_w else None,
            artist_region_box=(
                (artist_box["x"] - int(win_w * rl),
                 artist_box["y"] - int(win_h * rt),
                 artist_box["w"], artist_box["h"])
            ) if artist_box and win_w else None,
        )
        if not tracks:
            self._signals.error_occurred.emit("OCR 未识别到歌曲，请确认播放列表可见")
            return
        self._signals.track_detected.emit(tracks[0])

    def _capture_and_detect(self):
        if not self._running:
            return

        def worker():
            try:
                if not self._screen_capture.activate_window():
                    self._signals.error_occurred.emit("窗口激活失败，请确认 Apple Music 窗口存在")
                    return
                self._signals.window_activated.emit()
            except Exception as e:
                traceback.print_exc()
                self._signals.error_occurred.emit(f"识别异常: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def _handle_track_detected(self, track: TrackInfo):
        self._current_track = track
        self._track_card.set_track(track.display_text(), track.album)
        self._playlist_grid.set_buttons_active(True)

        missing = self._template_lib.get_missing_templates(self._config)
        missing_playlists = {
            name.split("/", 1)[1]
            for name in missing if name.startswith("playlists/")
        }
        self._playlist_grid.disable_missing_playlists(missing_playlists)

    def _on_classify(self, playlist_name: str, volume_name: str):
        if not self._running:
            return
        
        import sys
        # Use current_track if available, otherwise use cached dots position
        if self._current_track:
            dots_pos = self._current_track.dots_btn_pos
        else:
            # No OCR data — use cached position for the dots button
            region = self._template_lib.get_cached_region("position/more_button")
            if region:
                offset = (self._screen_capture._window_rect[:2]
                          if self._screen_capture._window_rect else (0, 0))
                cx = region["x"] + region["w"] // 2 + offset[0]
                cy = region["y"] + region["h"] // 2 + offset[1]
                dots_pos = (cx, cy)
            else:
                from core.models import TrackInfo
                dots_pos = (0, 0)
                self._current_track = TrackInfo("未知歌曲", "", "", 0, (0, 0))

        track = self._current_track
        self._playlist_grid.set_buttons_active(False)

        def worker():
            try:
                result = self._action_executor.classify_track(
                    dots_pos, playlist_name, volume_name,
                    track.song_name,
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

    # ─────────────────── Mood analysis ──────────────────────────────

    def _handle_mood_analyzed(self, arousal, valence, quadrant, confidence):
        self._quadrant_chart.update_mood(arousal, valence, quadrant, confidence)

        if confidence >= 0.6:
            self._playlist_grid.highlight_quadrant(quadrant)
            # Enable buttons so user can click highlighted playlists
            self._playlist_grid.set_buttons_active(True)
            tag_label = MOOD_LABELS.get(quadrant, quadrant)
            c = MOOD_COLORS.get(quadrant, {})
            self._set_status(tag_label, c.get('fg', '#1a73e8'),
                             c.get('bg', '#e8f0fe'), 600)
        else:
            self._playlist_grid.clear_highlight()
            if confidence > 0:
                pct = f"{confidence:.0%}"
                self._set_status(f"分析中... {pct}", "#5f6368", "#e8eaed")

    def _handle_analysis_error(self, msg: str):
        print(f"[ANALYSIS ERROR] {msg}", file=sys.stderr, flush=True)
        self._set_status("分析异常", "#c62828", "#fce4ec", 400)

    def _handle_boundary(self):
        self._playlist_grid.clear_highlight()
        self._quadrant_chart.show_boundary()
        self._set_status("检测到切歌，重新分析", "#e65100", "#fff3e0")

    def _handle_no_audio(self):
        self._playlist_grid.clear_highlight()
        self._quadrant_chart.reset()
        self._set_status("Apple Music 未在播放", "#9aa0a6", "#f1f3f4", 400)

    # ────────────────────── Errors ──────────────────────────────────

    def _handle_error(self, msg: str):
        print(f"[ERROR] {msg}", file=sys.stderr, flush=True)
        self._track_card.set_track(f"错误: {msg}", "")
        self._running = False
        self._sidebar.play_button.set_active(False)
        self._playlist_grid.set_buttons_active(False)

    # ─────────────────────── Dialogs ────────────────────────────────

    def _on_open_screenshot_library(self):
        lib = ScreenshotLibrary(
            self._template_lib, self._config, self._screen_capture, self,
        )
        lib.exec()
        QTimer.singleShot(100, self._reclaim_focus)

    def _reclaim_focus(self):
        """Force window to foreground using Windows API + ALT-key unlock."""
        try:
            hwnd = int(self.winId())
            # ALT key press to bypass Windows foreground lock
            ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)
            ctypes.windll.user32.keybd_event(0x12, 0, 2, 0)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            ctypes.windll.user32.BringWindowToTop(hwnd)
        except Exception:
            self.activateWindow()
            self.raise_()
        self.setFocus(Qt.OtherFocusReason)
        self.activateWindow()
        self.raise_()
