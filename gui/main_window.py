import sys
import traceback
import threading
import ctypes
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QFrame,
)
from PySide6.QtCore import Signal, QObject, Qt, QTimer, QRect, QPoint
from PySide6.QtGui import QGuiApplication, QIcon, QPainter, QColor, QPen, QFont

from core.models import TrackInfo, ClassificationResult
from core.screen_capture import ScreenCapture
from core.ocr_reader import OCRReader
from core.action_executor import ActionExecutor
from core.playlist_config import PlaylistConfig
from core.template_library import TemplateLibrary
from core.audio_capture import AudioCaptureManager
from core.audio_analyzer import AudioAnalyzer
from core.music2emo_client import Music2EmoClient
from process_audio_capture import ProcessAudioCapture

from gui.theme import MAIN_QSS
from gui.sidebar import Sidebar
from gui.track_card import TrackCard
from gui.playlist_grid import PlaylistGrid
from gui.quadrant_chart import QuadrantChart
from gui.spectrum_bar import SpectrumBar, _FFT_SIZE
from gui.screenshot_library import ScreenshotLibrary


class Signals(QObject):
    track_detected = Signal(object)
    classification_done = Signal(object)
    error_occurred = Signal(str)


class _OcrHighlightOverlay(QWidget):
    _COLORS = {
        "song": "#1a73e8",
        "artist": "#34a853",
        "album": "#f9ab00",
    }
    _DISPLAY_MS = 1500

    def __init__(self, rects: list[tuple[int, int, int, int, str]],
                 screen_geo: QRect, parent=None):
        super().__init__(parent)
        self._rects = rects
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Window
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setGeometry(screen_geo)
        QTimer.singleShot(self._DISPLAY_MS, self.close)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        for x, y, w, h, label in self._rects:
            color = QColor(self._COLORS.get(label, "#1a73e8"))
            painter.setPen(QPen(color, 3))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(x, y, w, h)
            if label:
                painter.setPen(color)
                font = QFont()
                font.setPixelSize(11)
                font.setWeight(QFont.Weight.Bold)
                painter.setFont(font)
                painter.drawText(x, y - 4, label)
        painter.end()


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
        m2e_cfg = config.music2emo_config
        self._m2e_client = (
            Music2EmoClient(m2e_cfg["venv_python"], m2e_cfg["server_script"])
            if m2e_cfg["enabled"] else None
        )
        self._audio_analyzer = AudioAnalyzer(self._audio_capture, self._m2e_client)

        # ── State ───────────────────────────────────────────────────
        self._current_track: TrackInfo | None = None
        self._running = False
        self._mood_active = False
        self._mood_unsupported = not ProcessAudioCapture.is_supported()
        self._ocr_overlay_widget: _OcrHighlightOverlay | None = None
        self._detecting = False
        self._classifying = False

        self.setWindowIcon(QIcon())

        # ── Build UI ────────────────────────────────────────────────
        self._init_ui()
        self._connect_signals()

    # ───────────────────────── UI ───────────────────────────────────

    def _init_ui(self):
        self.setWindowTitle("MusicClassifier")
        self.setFixedWidth(620)
        self.setFixedHeight(400)
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
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(6)

        self._track_card = TrackCard(self)
        main_layout.addWidget(self._track_card)

        main_layout.addSpacing(2)

        self._spectrum_bar = SpectrumBar(self)
        self._spectrum_bar.set_update_callback(self._spectrum_tick)
        main_layout.addWidget(self._spectrum_bar)

        main_layout.addSpacing(6)

        # ── Playlist grid (left) + Quadrant chart (right) ──────────
        bottom_container = QWidget()
        bottom_layout = QHBoxLayout(bottom_container)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(8)

        self._playlist_grid = PlaylistGrid(
            moods, self._volumes, self._on_classify, self,
        )
        self._playlist_grid.setFixedHeight(220)
        bottom_layout.addWidget(self._playlist_grid, 1)

        self._quadrant_chart = QuadrantChart(self)
        self._quadrant_chart.setFixedHeight(220)
        bottom_layout.addWidget(self._quadrant_chart, 1)

        main_layout.addWidget(bottom_container)
        main_layout.addStretch(1)

        body_layout.addWidget(main_area)
        outer_layout.addWidget(body)

    def _connect_signals(self):
        self._signals.track_detected.connect(self._handle_track_detected)
        self._signals.classification_done.connect(self._handle_classification_done)
        self._signals.error_occurred.connect(self._handle_error)
        self._audio_analyzer.signals.mood_analyzed.connect(self._handle_mood_analyzed)
        self._audio_analyzer.signals.analysis_error.connect(self._handle_analysis_error)
        self._audio_analyzer.signals.boundary_detected.connect(self._handle_boundary)
        self._audio_analyzer.signals.no_audio.connect(self._handle_no_audio)

    def showEvent(self, event):
        super().showEvent(event)

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
            self._spectrum_bar.stop()
        else:
            # Start OCR + audio
            if not self._screen_capture.find_window():
                print("[ERROR] 未找到 Apple Music 窗口，请先打开 Apple Music。",
                      file=sys.stderr, flush=True)
                return
            self._screen_capture.activate_window()
            self._sidebar.play_button.set_active(True)
            self._running = True
            self._capture_and_detect()
            # Start audio detection
            if not self._mood_unsupported:
                self._spectrum_bar.start()
                threading.Thread(target=self._start_audio, daemon=True).start()

    def _start_audio(self):
        if self._audio_capture.start():
            self._audio_analyzer.start()
            self._mood_active = True
        else:
            print("[AUDIO] 音频捕获启动失败", file=sys.stderr, flush=True)
            self._signals.error_occurred.emit("音频捕获启动失败，请检查 Apple Music 是否正在播放")

    def _spectrum_tick(self):
        import numpy as np
        mono = self._audio_capture.get_recent_samples(_FFT_SIZE)
        if mono is not None:
            mono = np.mean(mono, axis=0).astype(np.float32)
            levels = self._spectrum_bar.compute_fft(mono)
            self._spectrum_bar.update_levels(levels)

    def _capture_and_detect(self):
        if not self._running:
            return
        if self._detecting:
            return
        self._detecting = True

        def worker():
            try:
                if not self._screen_capture.activate_window():
                    self._signals.error_occurred.emit("窗口激活失败，请确认 Apple Music 窗口存在")
                    return
                image = self._screen_capture.capture_list_region(
                    delay_ms=self._config.before_screenshot_ms
                )
                if image is None:
                    self._signals.error_occurred.emit("截图失败，请确认 Apple Music 窗口可见")
                    return
                win_rect = self._screen_capture.get_window_rect()
                offset = (win_rect[:2] if win_rect else (0, 0))
                win_w = win_rect[2] - win_rect[0] if win_rect else 0
                win_h = win_rect[3] - win_rect[1] if win_rect else 0

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
            except Exception as e:
                traceback.print_exc()
                self._signals.error_occurred.emit(f"识别异常: {e}")
            finally:
                self._detecting = False

        threading.Thread(target=worker, daemon=True).start()

    def _handle_track_detected(self, track: TrackInfo):
        is_same_track = (
            self._current_track is not None
            and track.song_name == self._current_track.song_name
            and track.artist == self._current_track.artist
        )
        self._current_track = track
        if not is_same_track:
            self._track_card.set_track(track.song_name, track.artist, track.album)
            self._show_ocr_highlights(track)
            if self._mood_active:
                self._audio_analyzer.force_reset()
        self._playlist_grid.set_buttons_active(True)

        missing = self._template_lib.get_missing_templates(self._config)
        missing_playlists = {
            name.split("/", 1)[1]
            for name in missing if name.startswith("playlists/")
        }
        self._playlist_grid.disable_missing_playlists(missing_playlists)

    def _show_ocr_highlights(self, track: TrackInfo) -> None:
        if self._ocr_overlay_widget is not None:
            self._ocr_overlay_widget.close()
            self._ocr_overlay_widget = None

        if not track.ocr_boxes:
            print(f"[OCR] no ocr_boxes on track", file=sys.stderr, flush=True)
            return

        win_rect = self._screen_capture.get_window_rect()
        if not win_rect:
            return

        rl, rt, _, _ = self._screen_capture._list_region_ratio
        win_w = win_rect[2] - win_rect[0]
        win_h = win_rect[3] - win_rect[1]
        list_left_phys = win_rect[0] + int(win_w * rl)
        list_top_phys = win_rect[1] + int(win_h * rt)

        screen = QGuiApplication.screenAt(QPoint(win_rect[0], win_rect[1]))
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        dpr = screen.devicePixelRatio() if screen else 1.0

        rects: list[tuple[int, int, int, int, str]] = []
        for sx, sy, sw, sh, label in track.ocr_boxes:
            lx = int((list_left_phys + sx) / dpr)
            ly = int((list_top_phys + sy) / dpr)
            lw = max(int(sw / dpr), 16)
            lh = max(int(sh / dpr), 10)
            rects.append((lx, ly, lw, lh, label))
            print(f"[OCR] box: {label} screen=({lx},{ly},{lw},{lh}) dpr={dpr:.2f}",
                  file=sys.stderr, flush=True)

        geo = screen.geometry() if screen else QRect(0, 0, 1920, 1080)
        self._ocr_overlay_widget = _OcrHighlightOverlay(rects, geo, self)
        self._ocr_overlay_widget.show()

    def _on_classify(self, playlist_name: str, volume_name: str):
        import sys
        print(f"[MAIN] _on_classify: playlist='{playlist_name}' volume='{volume_name}' running={self._running}",
              file=sys.stderr, flush=True)
        if not self._running:
            print("[MAIN]  _running=False, aborting", file=sys.stderr, flush=True)
            return
        # Use current_track if available, otherwise use cached dots position
        if self._current_track:
            dots_pos = self._current_track.dots_btn_pos
        else:
            # No OCR data — use cached position for the dots button
            region = self._template_lib.get_cached_region("position/more_button")
            if region:
                wr = self._screen_capture.get_window_rect()
                offset = (wr[:2] if wr else (0, 0))
                cx = region["x"] + region["w"] // 2 + offset[0]
                cy = region["y"] + region["h"] // 2 + offset[1]
                dots_pos = (cx, cy)
            else:
                print("[MAIN] 无法确定三点按钮位置", file=sys.stderr, flush=True)
                self._signals.error_occurred.emit("无法确定三点按钮位置，请先执行 OCR 检测")
                return

        track = self._current_track
        self._playlist_grid.set_buttons_active(False)
        self._classifying = True

        def worker():
            try:
                result = self._action_executor.classify_track(
                    dots_pos, playlist_name, volume_name,
                    track.song_name if track else "未知歌曲",
                )
                self._signals.classification_done.emit(result)
            except Exception as e:
                traceback.print_exc()
                self._signals.error_occurred.emit(f"分类失败: {e}")
            finally:
                self._classifying = False

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
            self._playlist_grid.set_buttons_active(True)
        else:
            self._playlist_grid.clear_highlight()

    def _handle_analysis_error(self, msg: str):
        print(f"[ANALYSIS ERROR] {msg}", file=sys.stderr, flush=True)

    def _handle_boundary(self):
        self._playlist_grid.clear_highlight()
        self._quadrant_chart.show_boundary()
        if self._running and not self._classifying:
            self._capture_and_detect()

    def _handle_no_audio(self):
        self._playlist_grid.clear_highlight()
        self._quadrant_chart.reset()

    # ────────────────────── Errors ──────────────────────────────────

    def _handle_error(self, msg: str):
        print(f"[ERROR] {msg}", file=sys.stderr, flush=True)
        self._track_card.set_track(f"错误: {msg}")
        if self._running:
            self._playlist_grid.set_buttons_active(True)

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
