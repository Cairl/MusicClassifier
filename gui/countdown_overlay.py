"""Countdown overlay — shows a big number countdown before screenshot capture."""

from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont


class CountdownOverlay(QDialog):
    """Full-screen semi-transparent countdown (5→1) before capture."""

    def __init__(self, seconds: int = 5, parent=None):
        super().__init__(parent)
        self._remaining = seconds

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent;")

        screen = self.screen() if hasattr(self, 'screen') else None
        if screen:
            self.setGeometry(screen.geometry())
        else:
            self.setGeometry(0, 0, 1920, 1080)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        label_font = QFont()
        label_font.setPixelSize(120)
        label_font.setWeight(QFont.Weight.Bold)

        self._label = QLabel(str(seconds))
        self._label.setFont(label_font)
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setStyleSheet(
            "color: #ffffff; background-color: rgba(0,0,0,160); "
            "border-radius: 40px; padding: 20px 60px;"
        )
        layout.addWidget(self._label)

        hint = QLabel("请将鼠标移至目标区域上方")
        hint_font = QFont()
        hint_font.setPixelSize(16)
        hint.setFont(hint_font)
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("color: rgba(255,255,255,180); background: transparent;")
        layout.addWidget(hint)

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _tick(self):
        self._remaining -= 1
        if self._remaining <= 0:
            self._timer.stop()
            self.accept()
        else:
            self._label.setText(str(self._remaining))

    def keyPressEvent(self, event):
        """Escape cancels the countdown."""
        from PySide6.QtGui import QKeyEvent
        if event.key() == Qt.Key_Escape:
            self._timer.stop()
            self.reject()

    @staticmethod
    def countdown(seconds: int = 5, parent=None) -> bool:
        """Show countdown and block. Returns True if completed, False if cancelled."""
        dlg = CountdownOverlay(seconds, parent)
        return dlg.exec() == QDialog.Accepted
