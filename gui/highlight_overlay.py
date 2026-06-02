"""Highlight overlay — shows a brief red rectangle at click target, no separate window."""

from PySide6.QtWidgets import QDialog
from PySide6.QtCore import Qt, QTimer, QRect
from PySide6.QtGui import QPainter, QColor, QPen, QGuiApplication


class HighlightOverlay(QDialog):
    """Frameless overlay that draws a red rectangle on screen briefly."""

    def __init__(self, x: int, y: int, w: int = 40, h: int = 20,
                 label: str = "", duration_ms: int = 300, parent=None):
        super().__init__(parent)
        self._x = x
        self._y = y
        self._rw = w
        self._rh = h
        self._label = label

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setStyleSheet("background: transparent;")

        # Full-screen transparent overlay
        screen = QGuiApplication.primaryScreen()
        geo = screen.geometry() if screen else QRect(0, 0, 1920, 1080)
        self.setGeometry(geo)

        QTimer.singleShot(duration_ms, self.close)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        half_w, half_h = self._rw // 2, self._rh // 2
        x1 = self._x - half_w
        y1 = self._y - half_h
        x2 = self._x + half_w
        y2 = self._y + half_h

        # Red rectangle
        painter.setPen(QPen(QColor(255, 0, 0), 3))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(x1, y1, x2 - x1, y2 - y1)

        # Label above
        if self._label:
            painter.setPen(QColor(255, 0, 0))
            font = painter.font()
            font.setPixelSize(12)
            font.setWeight(font.Weight.Bold)
            painter.setFont(font)
            painter.drawText(x1, y1 - 16, self._label)

        painter.end()
