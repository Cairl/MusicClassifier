from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PySide6.QtCore import Qt, Signal, QPoint, QEvent
from PySide6.QtGui import QPainter, QPainterPath, QColor


class SettingsPopover(QWidget):
    template_capture_requested = Signal()
    about_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(160, 90)

        self._container = QWidget(self)
        self._container.setGeometry(6, 6, 148, 78)
        self._container.setStyleSheet(
            "background-color: #ffffff; border: none; border-radius: 12px;"
        )

        layout = QVBoxLayout(self._container)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(2)

        self._template_item = QLabel("模板采集")
        self._template_item.setFixedHeight(32)
        self._template_item.setCursor(Qt.PointingHandCursor)
        self._template_item.setAlignment(Qt.AlignVCenter)
        self._template_item.setStyleSheet(
            "padding: 0 12px; font-size: 12px; color: #202124; border-radius: 8px;"
        )

        self._about_item = QLabel("关于")
        self._about_item.setFixedHeight(32)
        self._about_item.setCursor(Qt.PointingHandCursor)
        self._about_item.setAlignment(Qt.AlignVCenter)
        self._about_item.setStyleSheet(
            "padding: 0 12px; font-size: 12px; color: #202124; border-radius: 8px;"
        )

        layout.addWidget(self._template_item)
        layout.addWidget(self._about_item)

        self._template_item.installEventFilter(self)
        self._about_item.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj in (self._template_item, self._about_item):
            if event.type() == QEvent.Enter:
                obj.setStyleSheet(
                    "padding: 0 12px; font-size: 12px; color: #202124;"
                    " border-radius: 8px; background-color: #e8eaed;"
                )
            elif event.type() == QEvent.Leave:
                obj.setStyleSheet(
                    "padding: 0 12px; font-size: 12px; color: #202124; border-radius: 8px;"
                )
            elif event.type() == QEvent.MouseButtonRelease:
                if obj is self._template_item:
                    self.template_capture_requested.emit()
                elif obj is self._about_item:
                    self.about_requested.emit()
                self.hide()
        return super().eventFilter(obj, event)

    def show_at(self, pos: QPoint):
        self.move(pos)
        self.show()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        shadow_path = QPainterPath()
        shadow_path.addRoundedRect(7, 8, 148, 78, 10, 10)
        painter.fillPath(shadow_path, QColor(0, 0, 0, 13))
        painter.end()
