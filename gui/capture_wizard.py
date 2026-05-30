import numpy as np
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QMessageBox,
)
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QImage, QPixmap
from core.screen_capture import ScreenCapture
from core.template_library import TemplateLibrary
from core.playlist_config import PlaylistConfig
from gui.screenshot_overlay import ScreenshotOverlay
import cv2


class CaptureWizard(QDialog):
    def __init__(self, screen_capture: ScreenCapture, template_lib: TemplateLibrary, config: PlaylistConfig, parent=None):
        super().__init__(parent)
        self._screen_capture = screen_capture
        self._template_lib = template_lib
        self._config = config
        self._steps = self._build_steps()
        self._current_step = 0
        self._cropped_image: np.ndarray | None = None
        self.setWindowTitle("模板采集向导")
        self.setMinimumSize(480, 420)
        self._init_ui()
        self._update_display()

    def _build_steps(self) -> list[dict]:
        steps = [
            {
                "name": "ui/add_to_playlist",
                "label": "UI 按钮: \"添加到播放列表\"",
                "instruction": "请右键 Apple Music 中任意歌曲，展开上下文菜单",
            }
        ]
        for vol_name in self._config.get_volumes():
            steps.append({
                "name": f"volumes/{vol_name}",
                "label": f"卷名: \"{vol_name}\"",
                "instruction": f"请右键歌曲 → 添加到播放列表，确保「{vol_name}」可见",
            })
        moods = self._config.get_all_moods_flat()
        for mood in moods:
            steps.append({
                "name": f"playlists/{mood['playlist']}",
                "label": f"歌单名: \"{mood['playlist']}\"",
                "instruction": f"请展开「{mood['volume']}」子菜单，确保「{mood['playlist']}」可见",
            })
        return steps

    def _init_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #fafafa;
            }
            QLabel {
                color: #202124;
            }
            QProgressBar {
                border: none;
                border-radius: 4px;
                background-color: #e8eaed;
                text-align: center;
                color: #202124;
            }
            QProgressBar::chunk {
                background-color: #5f6368;
                border-radius: 4px;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        self._step_label = QLabel()
        self._step_label.setStyleSheet("font-size: 15px; font-weight: 700; color: #202124;")
        layout.addWidget(self._step_label)

        self._name_label = QLabel()
        self._name_label.setStyleSheet("font-size: 13px; color: #5f6368; font-weight: 600;")
        layout.addWidget(self._name_label)

        self._instruction_label = QLabel()
        self._instruction_label.setWordWrap(True)
        self._instruction_label.setStyleSheet("font-size: 12px; color: #80868b;")
        layout.addWidget(self._instruction_label)

        self._preview_label = QLabel()
        self._preview_label.setMinimumSize(360, 120)
        self._preview_label.setAlignment(Qt.AlignCenter)
        self._preview_label.setStyleSheet("background-color: #ffffff; border: none; border-radius: 12px;")
        layout.addWidget(self._preview_label)

        btn_layout = QHBoxLayout()
        self._skip_btn = QPushButton("跳过")
        self._skip_btn.setStyleSheet("background-color: #e8eaed; color: #202124; border: none; border-radius: 8px; padding: 8px 16px; font-weight: 500;")
        self._skip_btn.clicked.connect(self._on_skip)
        self._capture_btn = QPushButton("截取选区")
        self._capture_btn.setStyleSheet("background-color: #5f6368; color: #ffffff; border: none; border-radius: 8px; padding: 8px 16px; font-weight: 600;")
        self._capture_btn.clicked.connect(self._on_capture)
        self._retake_btn = QPushButton("确认并重截")
        self._retake_btn.setStyleSheet("background-color: #e8eaed; color: #202124; border: none; border-radius: 8px; padding: 8px 16px; font-weight: 500;")
        self._retake_btn.clicked.connect(self._on_capture)
        self._retake_btn.setVisible(False)
        btn_layout.addWidget(self._skip_btn)
        btn_layout.addWidget(self._capture_btn)
        btn_layout.addWidget(self._retake_btn)
        layout.addLayout(btn_layout)

        self._progress = QProgressBar()
        self._progress.setMaximum(len(self._steps))
        layout.addWidget(self._progress)

    def _update_display(self):
        if self._current_step >= len(self._steps):
            self.accept()
            return
        step = self._steps[self._current_step]
        total = len(self._steps)
        self._step_label.setText(f"模板采集向导 ({self._current_step + 1}/{total})")
        self._name_label.setText(f"当前需要采集: {step['label']}")
        self._instruction_label.setText(step["instruction"])
        self._progress.setValue(self._current_step)
        self._cropped_image = None
        self._preview_label.setText("尚未截取")
        self._preview_label.setPixmap(QPixmap())
        self._retake_btn.setVisible(False)
        self._capture_btn.setText("截取选区")

    def _on_capture(self):
        self.hide()
        screenshot = self._screen_capture.capture_full_screen(delay_ms=500)
        self.show()
        if screenshot is None:
            QMessageBox.warning(self, "错误", "截图失败")
            return

        overlay = ScreenshotOverlay(screenshot, self)
        overlay.region_selected.connect(self._handle_overlay_captured)
        overlay.cancelled.connect(self._on_overlay_cancelled)
        overlay.exec()

    def _handle_overlay_captured(self, rect: QRect):
        screenshot = self._screen_capture.capture_full_screen(delay_ms=500)
        if screenshot is None:
            QMessageBox.warning(self, "错误", "截图失败")
            return
        x1, y1 = rect.x(), rect.y()
        x2, y2 = x1 + rect.width(), y1 + rect.height()
        x1, x2 = max(0, x1), min(screenshot.shape[1], x2)
        y1, y2 = max(0, y1), min(screenshot.shape[0], y2)
        cropped = screenshot[y1:y2, x1:x2]
        if cropped.size == 0:
            return
        self._cropped_image = cropped
        h, w = cropped.shape[:2]
        rgb = cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, w, h, w * 3, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg.copy())
        scaled = pixmap.scaled(self._preview_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._preview_label.setPixmap(scaled)
        self._retake_btn.setVisible(True)
        self._capture_btn.setText("确认并继续")
        try:
            self._capture_btn.clicked.disconnect()
        except RuntimeError:
            pass
        self._capture_btn.clicked.connect(self._on_confirm_and_next)

    def _on_overlay_cancelled(self):
        pass

    def _on_confirm_and_next(self):
        if self._cropped_image is None:
            return
        step = self._steps[self._current_step]
        self._template_lib.save_template(step["name"], self._cropped_image)
        self._current_step += 1
        try:
            self._capture_btn.clicked.disconnect()
        except RuntimeError:
            pass
        self._capture_btn.clicked.connect(self._on_capture)
        self._update_display()

    def _on_skip(self):
        self._current_step += 1
        self._update_display()
