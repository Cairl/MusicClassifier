import threading
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QTextEdit, QProgressBar,
    QGroupBox, QMessageBox,
)
from PySide6.QtCore import Signal, QObject
from core.models import TrackInfo, ClassificationResult
from core.screen_capture import ScreenCapture
from core.ocr_reader import OCRReader
from core.action_executor import ActionExecutor
from core.playlist_config import PlaylistConfig


class Signals(QObject):
    track_detected = Signal(object)
    classification_done = Signal(object)
    log_message = Signal(str)
    error_occurred = Signal(str)
    progress_updated = Signal(int, int)


class MainWindow(QMainWindow):
    def __init__(self, config: PlaylistConfig):
        super().__init__()
        self._config = config
        self._signals = Signals()
        self._screen_capture = ScreenCapture(config.window_title)
        self._ocr_reader = OCRReader()
        self._action_executor = ActionExecutor(
            self._screen_capture,
            self._ocr_reader,
            after_click_ms=config.after_click_ms,
            menu_appear_ms=config.menu_appear_ms,
        )
        self._current_track: TrackInfo | None = None
        self._processed = 0
        self._total = 0
        self._running = False
        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        self.setWindowTitle("MusicClassifier")
        self.setMinimumSize(500, 600)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        track_group = QGroupBox("当前歌曲")
        track_layout = QVBoxLayout(track_group)
        self._track_label = QLabel("等待识别...")
        self._track_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        self._album_label = QLabel("")
        self._album_label.setStyleSheet("color: gray;")
        track_layout.addWidget(self._track_label)
        track_layout.addWidget(self._album_label)
        layout.addWidget(track_group)

        classify_group = QGroupBox("分类到")
        classify_layout = QHBoxLayout(classify_group)
        classify_layout.addWidget(QLabel("歌单:"))
        self._playlist_combo = QComboBox()
        self._playlist_combo.addItems(self._config.get_all_playlists())
        classify_layout.addWidget(self._playlist_combo)
        layout.addWidget(classify_group)

        btn_layout = QHBoxLayout()
        self._classify_btn = QPushButton("分类此首")
        self._classify_btn.setEnabled(False)
        self._classify_btn.setStyleSheet("background-color: #e74c3c; color: white; font-weight: bold; padding: 8px;")
        btn_layout.addWidget(self._classify_btn)
        self._skip_btn = QPushButton("跳过")
        self._skip_btn.setEnabled(False)
        btn_layout.addWidget(self._skip_btn)
        self._recapture_btn = QPushButton("重新截图")
        self._recapture_btn.setEnabled(False)
        btn_layout.addWidget(self._recapture_btn)
        self._start_btn = QPushButton("开始")
        self._start_btn.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold; padding: 8px;")
        btn_layout.addWidget(self._start_btn)
        layout.addLayout(btn_layout)

        log_group = QGroupBox("操作日志")
        log_layout = QVBoxLayout(log_group)
        self._log_text = QTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setMaximumHeight(200)
        log_layout.addWidget(self._log_text)
        layout.addWidget(log_group)

        self._progress_bar = QProgressBar()
        self._progress_bar.setValue(0)
        layout.addWidget(self._progress_bar)

        self._classify_btn.clicked.connect(self._on_classify)
        self._skip_btn.clicked.connect(self._on_skip)
        self._recapture_btn.clicked.connect(self._on_recapture)
        self._start_btn.clicked.connect(self._on_start)

    def _connect_signals(self):
        self._signals.track_detected.connect(self._handle_track_detected)
        self._signals.classification_done.connect(self._handle_classification_done)
        self._signals.log_message.connect(self._handle_log)
        self._signals.error_occurred.connect(self._handle_error)
        self._signals.progress_updated.connect(self._handle_progress)

    def _on_start(self):
        if not self._screen_capture.find_window():
            QMessageBox.warning(self, "错误", "未找到 Apple Music 窗口，请先打开 Apple Music。")
            return
        self._screen_capture.activate_window()
        self._start_btn.setEnabled(False)
        self._classify_btn.setEnabled(True)
        self._skip_btn.setEnabled(True)
        self._recapture_btn.setEnabled(True)
        self._running = True
        self._processed = 0
        self._total = 0
        self._capture_and_detect()

    def _capture_and_detect(self):
        if not self._running:
            return

        def worker():
            self._screen_capture.activate_window()
            image = self._screen_capture.capture_list_region(delay_ms=self._config.before_screenshot_ms)
            if image is None:
                self._signals.error_occurred.emit("截图失败，请确认 Apple Music 窗口可见")
                return
            offset = self._screen_capture._window_rect[:2] if self._screen_capture._window_rect else (0, 0)
            tracks = self._ocr_reader.read_tracks(image, offset)
            if not tracks:
                self._signals.error_occurred.emit("OCR 未识别到歌曲，请确认歌单列表可见")
                return
            if self._total == 0:
                self._total = len(tracks)
            self._signals.track_detected.emit(tracks[0])

        threading.Thread(target=worker, daemon=True).start()

    def _handle_track_detected(self, track: TrackInfo):
        self._current_track = track
        self._track_label.setText(track.display_text())
        self._album_label.setText(f"专辑: {track.album}" if track.album else "")
        self._signals.log_message.emit(f"识别到歌曲: {track.display_text()}")

    def _on_classify(self):
        if not self._current_track:
            return
        display = self._playlist_combo.currentText()
        playlist_name = self._config.get_playlist_name_from_display(display)
        track = self._current_track
        self._classify_btn.setEnabled(False)
        self._skip_btn.setEnabled(False)
        self._recapture_btn.setEnabled(False)

        def worker():
            result = self._action_executor.classify_track(
                track.dots_btn_pos, playlist_name, track.song_name
            )
            self._processed += 1
            self._signals.classification_done.emit(result)

        threading.Thread(target=worker, daemon=True).start()

    def _handle_classification_done(self, result: ClassificationResult):
        self._signals.log_message.emit(result.message)
        self._signals.progress_updated.emit(self._processed, self._total)
        self._classify_btn.setEnabled(True)
        self._skip_btn.setEnabled(True)
        self._recapture_btn.setEnabled(True)
        self._capture_and_detect()

    def _on_skip(self):
        self._processed += 1
        self._signals.log_message.emit(f"跳过: {self._current_track.display_text() if self._current_track else '?'}")
        self._signals.progress_updated.emit(self._processed, self._total)
        self._capture_and_detect()

    def _on_recapture(self):
        self._capture_and_detect()

    def _handle_log(self, msg: str):
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._log_text.append(f"[{timestamp}] {msg}")

    def _handle_error(self, msg: str):
        self._signals.log_message.emit(f"❌ {msg}")
        self._classify_btn.setEnabled(True)
        self._skip_btn.setEnabled(True)
        self._recapture_btn.setEnabled(True)

    def _handle_progress(self, done: int, total: int):
        if total > 0:
            self._progress_bar.setMaximum(total)
            self._progress_bar.setValue(done)
