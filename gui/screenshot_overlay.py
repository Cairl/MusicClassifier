import numpy as np
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QWidget
from PySide6.QtCore import Qt, QPoint, QRect, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QMouseEvent, QKeyEvent, QScreen, QGuiApplication, QImage, QPixmap, QPainterPath


class ScreenshotOverlay(QDialog):
    region_selected = Signal(QRect)
    cancelled = Signal()

    def __init__(self, screenshot: np.ndarray, parent=None):
        super().__init__(parent)
        self._screenshot = screenshot
        self._h, self._w = screenshot.shape[:2]
        self._selecting = False
        self._start_point: QPoint | None = None
        self._end_point: QPoint | None = None
        self._confirmed_rect: QRect | None = None
        self._background_pixmap: QPixmap | None = None
        screen = QGuiApplication.primaryScreen()
        self._dpr = screen.devicePixelRatio() if screen else 1.0
        self._init_ui()
        self._init_background()

    def _init_ui(self):
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Dialog
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)
        self.setFocusPolicy(Qt.StrongFocus)

        screen = QGuiApplication.primaryScreen()
        if screen:
            geo = screen.geometry()
            self.setGeometry(geo)
        else:
            self.setGeometry(0, 0, self._w, self._h)

    def _init_background(self):
        # Screenshot is RGB from pyautogui, display directly
        h, w = self._screenshot.shape[:2]
        rgb = self._screenshot
        qimg = QImage(rgb.data, w, h, w * 3, QImage.Format_RGB888)
        self._background_pixmap = QPixmap.fromImage(qimg.copy())

        self._toolbar = QWidget(self)
        self._toolbar.setVisible(False)
        self._toolbar.setStyleSheet(
            "background-color: #ffffff; border: none; border-radius: 12px; padding: 4px;"
        )
        toolbar_layout = QHBoxLayout(self._toolbar)
        toolbar_layout.setContentsMargins(8, 4, 8, 4)
        toolbar_layout.setSpacing(8)

        self._size_label = QLabel("")
        self._size_label.setStyleSheet("color: #202124; font-size: 12px; font-weight: 500;")
        toolbar_layout.addWidget(self._size_label)

        confirm_btn = QPushButton("确认")
        confirm_btn.setStyleSheet(
            "background-color: #5f6368; color: #ffffff; border: none; "
            "border-radius: 8px; padding: 4px 12px; font-size: 12px; font-weight: 600;"
        )
        confirm_btn.clicked.connect(self._on_confirm)
        toolbar_layout.addWidget(confirm_btn)

        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet(
            "background-color: #e8eaed; color: #202124; border: none; "
            "border-radius: 8px; padding: 4px 12px; font-size: 12px; font-weight: 500;"
        )
        cancel_btn.clicked.connect(self._on_cancel)
        toolbar_layout.addWidget(cancel_btn)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if self._background_pixmap:
            painter.drawPixmap(self.rect(), self._background_pixmap)

        # Dark semi-transparent overlay with a cutout for the selection
        overlay = QColor(0, 0, 0, 140)

        if self._start_point and self._end_point:
            rect = QRect(self._start_point, self._end_point).normalized()
            # Subtract the selected region from the overlay
            path = QPainterPath()
            path.addRect(self.rect())
            hole = QPainterPath()
            hole.addRect(rect)
            path = path.subtracted(hole)
            painter.fillPath(path, overlay)

            # White border around selected region
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect)

            # Crosshair center markers
            painter.setPen(QPen(QColor(255, 255, 255, 120), 1))
            self._draw_crosshair(painter, rect)
        else:
            # No selection yet — cover entire screen
            painter.fillRect(self.rect(), overlay)

        painter.end()

    def _draw_crosshair(self, painter: QPainter, rect: QRect):
        cx = rect.center().x()
        cy = rect.center().y()
        dash_len = 6
        gap_len = 4

        def draw_dashed_line(x1, y1, x2, y2):
            dx = x2 - x1
            dy = y2 - y1
            dist = (dx * dx + dy * dy) ** 0.5
            if dist == 0:
                return
            ux, uy = dx / dist, dy / dist
            pos = 0
            draw = True
            while pos < dist:
                seg = dash_len if draw else gap_len
                seg = min(seg, dist - pos)
                x_start = x1 + ux * pos
                y_start = y1 + uy * pos
                x_end = x1 + ux * (pos + seg)
                y_end = y1 + uy * (pos + seg)
                if draw:
                    painter.drawLine(int(x_start), int(y_start), int(x_end), int(y_end))
                pos += seg
                draw = not draw

        draw_dashed_line(rect.left(), cy, rect.left() - 20, cy)
        draw_dashed_line(rect.right(), cy, rect.right() + 20, cy)
        draw_dashed_line(cx, rect.top(), cx, rect.top() - 20)
        draw_dashed_line(cx, rect.bottom(), cx, rect.bottom() + 20)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._selecting = True
            self._start_point = event.pos()
            self._end_point = event.pos()
            self._toolbar.setVisible(False)
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._selecting:
            self._end_point = event.pos()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton and self._selecting:
            self._selecting = False
            self._end_point = event.pos()
            rect = QRect(self._start_point, self._end_point).normalized()
            if rect.width() > 5 and rect.height() > 5:
                self._confirmed_rect = rect
                self._size_label.setText(f"{rect.width()} x {rect.height()}")
                self._position_toolbar(rect)
                self._toolbar.setVisible(True)
            self.update()

    def _position_toolbar(self, rect: QRect):
        toolbar_w = self._toolbar.sizeHint().width()
        toolbar_h = self._toolbar.sizeHint().height()
        x = rect.center().x() - toolbar_w // 2
        y = rect.bottom() + 8
        if y + toolbar_h > self.height():
            y = rect.top() - toolbar_h - 8
        if x < 0:
            x = 0
        if x + toolbar_w > self.width():
            x = self.width() - toolbar_w
        self._toolbar.move(x, y)

    def _on_confirm(self):
        if self._confirmed_rect:
            # Scale from Qt device-independent pixels to physical pixels
            r = self._confirmed_rect
            rect = QRect(
                int(r.x() * self._dpr),
                int(r.y() * self._dpr),
                int(r.width() * self._dpr),
                int(r.height() * self._dpr),
            )
            self.region_selected.emit(rect)
        self.close()

    def _on_cancel(self):
        self.cancelled.emit()
        self.close()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Escape:
            self._on_cancel()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._on_confirm()

    def showEvent(self, event):
        self.activateWindow()
        self.setFocus(Qt.OtherFocusReason)
        self.grabKeyboard()
        super().showEvent(event)

    def hideEvent(self, event):
        self.releaseKeyboard()
        super().hideEvent(event)

    def get_selected_region(self) -> QRect | None:
        return self._confirmed_rect
