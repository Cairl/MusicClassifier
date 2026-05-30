from PySide6.QtWidgets import QToolButton
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor


class IconButton(QToolButton):
    def __init__(self, parent=None, color="#5f6368", icon_text=""):
        super().__init__(parent)
        self._base_color = QColor(color)
        self._icon_text = icon_text
        self.setFixedSize(28, 28)
        self.setCursor(Qt.PointingHandCursor)
        self.setText(icon_text)
        self.setStyleSheet(self._build_qss(color))

    def _build_qss(self, color: str) -> str:
        return f"""
            QToolButton {{
                background-color: #e0e0e0;
                color: {color};
                border: none;
                border-radius: 14px;
                font-size: 14px;
                font-weight: 500;
            }}
            QToolButton:hover {{
                background-color: #dadce0;
            }}
            QToolButton:pressed {{
                background-color: #c4c7c9;
            }}
            QToolButton:disabled {{
                background-color: #f1f3f4;
                color: #9aa0a6;
            }}
        """

    def setColor(self, color: str):
        self._base_color = QColor(color)
        self.setStyleSheet(self._build_qss(color))
