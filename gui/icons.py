"""
SVG path icon utilities for MusicClassifier.

Draws basic SVG path commands onto QPixmap to produce QIcon objects.
Used to avoid external icon font dependencies.
"""

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen, QPainterPath, QGuiApplication

from gui.theme import COLOR_SECONDARY, SIDEBAR_ICON_SIZE


def _draw_svg(size: int, color: str, paths: list[str], fill: bool = False) -> QIcon:
    """Render a list of SVG path strings onto a square QPixmap → QIcon.
    High-DPI aware: renders at screen's device pixel ratio."""
    screen = QGuiApplication.primaryScreen()
    dpr = screen.devicePixelRatio() if screen else 1.0
    px_size = max(int(size * dpr), 1)
    pixmap = QPixmap(px_size, px_size)
    pixmap.setDevicePixelRatio(dpr)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color))
    pen.setWidthF(1.5)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    if fill:
        painter.setBrush(QColor(color))
    else:
        painter.setBrush(Qt.BrushStyle.NoBrush)

    for path_data in paths:
        path = QPainterPath()
        parts = path_data.split()
        i = 0
        while i < len(parts):
            cmd = parts[i]
            if cmd == "M":
                path.moveTo(float(parts[i + 1]), float(parts[i + 2]))
                i += 3
            elif cmd == "L":
                path.lineTo(float(parts[i + 1]), float(parts[i + 2]))
                i += 3
            elif cmd == "C":
                path.cubicTo(
                    float(parts[i + 1]), float(parts[i + 2]),
                    float(parts[i + 3]), float(parts[i + 4]),
                    float(parts[i + 5]), float(parts[i + 6]),
                )
                i += 7
            elif cmd == "Q":
                path.quadTo(
                    float(parts[i + 1]), float(parts[i + 2]),
                    float(parts[i + 3]), float(parts[i + 4]),
                )
                i += 5
            elif cmd == "A":
                path.arcTo(
                    float(parts[i + 1]) - float(parts[i + 3]),
                    float(parts[i + 2]) - float(parts[i + 4]),
                    float(parts[i + 3]) * 2, float(parts[i + 4]) * 2,
                    float(parts[i + 5]), float(parts[i + 6]),
                )
                i += 7
            elif cmd == "Z":
                path.closeSubpath()
                i += 1
            else:
                i += 1
        painter.drawPath(path)
    painter.end()
    return QIcon(pixmap)


# ── Icon path data ─────────────────────────────────────────────────

_PLAY = ["M 7 4 L 16 10 L 7 16 Z"]

_LIBRARY = [
    "M 3 6 L 17 6 L 17 17 L 3 17 Z",   # body
    "M 7 6 L 9 4 L 11 4 L 13 6",        # top tab
]

_ABOUT = [
    "M 10 5 L 10 7",    # dot
    "M 10 9 L 10 16",   # stem
]

_SETTINGS = [
    "M 5 7 L 15 7",
    "M 5 10 L 15 10",
    "M 5 13 L 15 13",
]

_RECORD = [
    "M 5 10 Q 5 4 10 4 Q 15 4 15 10 L 15 12 L 5 12 Z",
    "M 3 12 L 3 14 Q 3 17 6 17 L 8 17 L 8 14",
    "M 17 12 L 17 14 Q 17 17 14 17 L 12 17 L 12 14",
    "M 8 17 L 8 19 L 12 19 L 12 17",
]


def play_icon(color: str = COLOR_SECONDARY, size: int = SIDEBAR_ICON_SIZE) -> QIcon:
    """Play triangle icon."""
    return _draw_svg(size, color, _PLAY, fill=True)


def library_icon(color: str = COLOR_SECONDARY, size: int = SIDEBAR_ICON_SIZE) -> QIcon:
    """Folder/library icon for screenshot library."""
    return _draw_svg(size, color, _LIBRARY)


def about_icon(color: str = COLOR_SECONDARY, size: int = SIDEBAR_ICON_SIZE) -> QIcon:
    """Lowercase 'i' icon for about."""
    return _draw_svg(size, color, _ABOUT)


def settings_icon(color: str = COLOR_SECONDARY, size: int = SIDEBAR_ICON_SIZE) -> QIcon:
    """Three horizontal lines icon."""
    return _draw_svg(size, color, _SETTINGS)


def record_icon(color: str = COLOR_SECONDARY, size: int = SIDEBAR_ICON_SIZE) -> QIcon:
    """Microphone icon."""
    return _draw_svg(size, color, _RECORD)
