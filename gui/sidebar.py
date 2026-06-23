"""Sidebar component — play and library buttons using SVG icons."""

import functools
import os

from PySide6.QtCore import Qt, Signal, QSize, QRectF
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton
from PySide6.QtGui import QIcon, QPixmap, QPainter, QGuiApplication
from PySide6.QtSvg import QSvgRenderer

from gui.theme import (
    COLOR_SECONDARY, COLOR_SEPARATOR,
    SIDEBAR_WIDTH, SIDEBAR_BUTTON_SIZE, SIDEBAR_ICON_SIZE,
    RADIUS_CIRCLE, COLOR_BTN_FILL_PRESSED, COLOR_BTN_FILL_HOVER,
)


_ASSETS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "icons")


@functools.lru_cache(maxsize=8)
def _svg_icon(path: str, color: str = COLOR_SECONDARY, size: int = 24) -> QIcon:
    with open(path, 'r', encoding='utf-8') as f:
        svg_data = f.read().replace('currentColor', color)
    renderer = QSvgRenderer(svg_data.encode('utf-8'))
    screen = QGuiApplication.primaryScreen()
    dpr = screen.devicePixelRatio() if screen else 1.0
    pixmap = QPixmap(int(size * dpr), int(size * dpr))
    pixmap.setDevicePixelRatio(dpr)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    return QIcon(pixmap)


_PLAY_SVG = os.path.join(_ASSETS, "play.svg")
_STOP_SVG = os.path.join(_ASSETS, "stop.svg")
_LIB_SVG = os.path.join(_ASSETS, "library.svg")

_SIDEBAR_BTN_QSS = f"""
    QPushButton {{
        background-color: transparent;
        border: none;
        border-radius: {RADIUS_CIRCLE};
        padding: 0px;
        margin: 0px;
    }}
    QPushButton:hover {{
        background-color: {COLOR_SEPARATOR};
    }}
    QPushButton:pressed {{
        background-color: {COLOR_BTN_FILL_PRESSED};
    }}
"""

_SIDEBAR_BTN_ACTIVE_QSS = f"""
    QPushButton {{
        background-color: {COLOR_SEPARATOR};
        border: none;
        border-radius: {RADIUS_CIRCLE};
        padding: 0px;
        margin: 0px;
    }}
    QPushButton:hover {{
        background-color: {COLOR_BTN_FILL_HOVER};
    }}
    QPushButton:pressed {{
        background-color: {COLOR_BTN_FILL_PRESSED};
    }}
"""


class SidebarButton(QPushButton):

    def __init__(self, icon: QIcon, icon_active: QIcon | None = None,
                 tooltip: str = "", parent=None):
        super().__init__(parent)
        self.setFixedSize(SIDEBAR_BUTTON_SIZE, SIDEBAR_BUTTON_SIZE)
        self._icon = icon
        self._icon_active = icon_active or icon
        self.setIcon(self._icon)
        self.setIconSize(QSize(SIDEBAR_ICON_SIZE, SIDEBAR_ICON_SIZE))
        self.setToolTip(tooltip)
        self.setStyleSheet(_SIDEBAR_BTN_QSS)
        self._active = False

    def set_active(self, active: bool) -> None:
        self._active = active
        self.setIcon(self._icon_active if active else self._icon)
        self.setStyleSheet(_SIDEBAR_BTN_ACTIVE_QSS if active else _SIDEBAR_BTN_QSS)


class Sidebar(QWidget):
    play_toggled = Signal()
    screenshot_library_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(SIDEBAR_WIDTH)

        margin = (SIDEBAR_WIDTH - SIDEBAR_BUTTON_SIZE) // 2
        layout = QVBoxLayout(self)
        layout.setContentsMargins(margin, 10, margin, 10)
        layout.setSpacing(4)

        play_icon = _svg_icon(_PLAY_SVG, size=SIDEBAR_ICON_SIZE)
        stop_icon = _svg_icon(_STOP_SVG, size=SIDEBAR_ICON_SIZE)
        self._play_btn = SidebarButton(play_icon, stop_icon, "开始 / 暂停", self)
        self._play_btn.clicked.connect(self.play_toggled.emit)
        layout.addWidget(self._play_btn, 0, Qt.AlignHCenter)

        lib_icon = _svg_icon(_LIB_SVG, size=SIDEBAR_ICON_SIZE)
        self._library_btn = SidebarButton(lib_icon, tooltip="截图库", parent=self)
        self._library_btn.clicked.connect(self.screenshot_library_requested.emit)
        layout.addWidget(self._library_btn, 0, Qt.AlignHCenter)

        layout.addStretch()

    @property
    def play_button(self) -> SidebarButton:
        return self._play_btn
