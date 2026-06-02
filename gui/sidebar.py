"""Sidebar component — play and library buttons using SVG icons."""

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton
from PySide6.QtGui import QIcon, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer

from gui.theme import COLOR_SECONDARY, COLOR_SEPARATOR, SIDEBAR_WIDTH


_ASSETS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "icons")


def _svg_icon(path: str, color: str = COLOR_SECONDARY, size: int = 22) -> QIcon:
    """Load SVG file and render as QIcon with specified fill color."""
    with open(path, 'r', encoding='utf-8') as f:
        svg_data = f.read().replace('currentColor', color)
    renderer = QSvgRenderer(svg_data.encode('utf-8'))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


_PLAY_SVG = os.path.join(_ASSETS, "play.svg")
_STOP_SVG = os.path.join(_ASSETS, "stop.svg")
_LIB_SVG = os.path.join(_ASSETS, "library.svg")


_BTN_SIZE = 34
_BTN_QSS = f"""
    QPushButton {{
        background-color: transparent;
        border: none;
        border-radius: 7px;
        padding: 0px;
        margin: 0px;
    }}
    QPushButton:hover {{
        background-color: {COLOR_SEPARATOR};
    }}
    QPushButton:pressed {{
        background-color: #dadce0;
    }}
"""


class SidebarButton(QPushButton):
    """A 34×34 flat icon button for the sidebar."""

    def __init__(self, icon: QIcon, icon_active: QIcon | None = None,
                 tooltip: str = "", parent=None):
        super().__init__(parent)
        self.setFixedSize(_BTN_SIZE, _BTN_SIZE)
        self._icon = icon
        self._icon_active = icon_active or icon
        self.setIcon(self._icon)
        self.setIconSize(icon.pixmap(22, 22).size())
        self.setToolTip(tooltip)
        self.setStyleSheet(_BTN_QSS)
        self._active = False

    def set_active(self, active: bool) -> None:
        self._active = active
        self.setIcon(self._icon_active if active else self._icon)


class Sidebar(QWidget):
    """Fixed-width column with play and library buttons at the top."""

    play_toggled = Signal()
    screenshot_library_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(SIDEBAR_WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(7, 10, 7, 10)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignHCenter)

        # Play / Pause button
        play_icon = _svg_icon(_PLAY_SVG, size=22)
        stop_icon = _svg_icon(_STOP_SVG, size=22)
        self._play_btn = SidebarButton(play_icon, stop_icon, "开始 / 暂停", self)
        self._play_btn.clicked.connect(self.play_toggled.emit)
        layout.addWidget(self._play_btn, 0, Qt.AlignHCenter)

        # Library button (always uses library.svg, no state)
        lib_icon = _svg_icon(_LIB_SVG, size=22)
        self._library_btn = SidebarButton(lib_icon, tooltip="截图库", parent=self)
        self._library_btn.clicked.connect(self.screenshot_library_requested.emit)
        layout.addWidget(self._library_btn, 0, Qt.AlignHCenter)

        layout.addStretch()

    @property
    def play_button(self) -> SidebarButton:
        return self._play_btn
