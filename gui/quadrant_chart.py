"""Quadrant chart — modern valence-arousal mood visualization with flat colors and bilingual labels."""

from PySide6.QtWidgets import QWidget, QSizePolicy
from PySide6.QtCore import Qt, QPointF, QTimer, QSize
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QPainterPath


# Flat modern quadrant colors
_QUADRANT_COLORS = {
    "CALM":       "#D5E8D4",  # sage
    "VIGOROUS":   "#FFE0B2",  # amber
    "MELANCHOLY": "#D7CCE8",  # lavender
    "TENSE":      "#F8CECC",  # rose
}

_QUADRANT_ACTIVE = {
    "CALM":       "#A8C7A6",
    "VIGOROUS":   "#FFC107",
    "MELANCHOLY": "#B39DDB",
    "TENSE":      "#EF9A9A",
}

_QUADRANT_FG = {
    "CALM":       "#2E7D32",
    "VIGOROUS":   "#E65100",
    "MELANCHOLY": "#4527A0",
    "TENSE":      "#C62828",
}

# Bilingual labels: (Chinese, English, chinese font size, english font size)
_QUADRANT_LABELS = {
    "CALM":       ("平静", "CALM"),
    "VIGOROUS":   ("活力", "VIGOR"),
    "MELANCHOLY": ("忧郁", "MELAN"),
    "TENSE":      ("紧张", "TENSE"),
}

_CONFIDENCE_THRESHOLD = 0.6
_DOT_SIZE = 10
_DOT_BORDER = 3
_ANIM_DURATION_MS = 700


class QuadrantChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._arousal: float = 0.0
        self._valence: float = 0.0
        self._quadrant: str = ""
        self._confidence: float = 0.0
        self._dot_visible: bool = False
        self._dot_x: float = 0.0
        self._dot_y: float = 0.0
        self._target_x: float = 0.0
        self._target_y: float = 0.0
        self._boundary_flash: bool = False
        self._anim_progress: float = 1.0

        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(16)
        self._anim_timer.timeout.connect(self._tick_anim)

        self._anim_start_x: float = 0.0
        self._anim_start_y: float = 0.0
        self._anim_elapsed: int = 0

        self._dot_x = self._dot_y = -100

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return width

    def sizeHint(self):
        return self.minimumSizeHint()

    def minimumSizeHint(self):
        return QSize(80, 80)

    @property
    def recommended_quadrant(self) -> str | None:
        if self._confidence >= _CONFIDENCE_THRESHOLD and self._quadrant:
            return self._quadrant
        return None

    def _chart_rect(self) -> tuple[int, int, int, int]:
        w = self.width()
        h = self.height()
        side = min(w, h - 14)
        ox = (w - side) // 2
        oy = (h - side) // 2
        return ox, oy, side, side

    def update_mood(self, arousal: float, valence: float, quadrant: str, confidence: float) -> None:
        self._arousal = arousal
        self._valence = valence
        self._quadrant = quadrant
        self._confidence = confidence
        self._dot_visible = True

        target_x, target_y = self._dot_pixel_pos(arousal, valence)

        self._anim_start_x = self._dot_x if self._dot_x >= 0 else target_x
        self._anim_start_y = self._dot_y if self._dot_y >= 0 else target_y

        self._target_x = target_x
        self._target_y = target_y
        self._anim_elapsed = 0
        self._anim_progress = 0.0
        self._anim_timer.start()

    def reset(self) -> None:
        self._arousal = 0.0
        self._valence = 0.0
        self._quadrant = ""
        self._confidence = 0.0
        self._dot_visible = False
        self._boundary_flash = False
        self._anim_timer.stop()
        self._anim_progress = 1.0
        self.update()

    def show_boundary(self) -> None:
        self._boundary_flash = True
        self.update()

    def _dot_pixel_pos(self, arousal: float | None = None, valence: float | None = None) -> tuple[float, float]:
        a = arousal if arousal is not None else self._arousal
        v = valence if valence is not None else self._valence
        ox, oy, side, _ = self._chart_rect()
        half = side / 2.0
        x = ox + half + v * half
        y = oy + half - a * half
        return x, y

    def _tick_anim(self) -> None:
        self._anim_elapsed += 16
        t = min(self._anim_elapsed / _ANIM_DURATION_MS, 1.0)
        self._anim_progress = self._ease_out(t)

        self._dot_x = self._anim_start_x + (self._target_x - self._anim_start_x) * self._anim_progress
        self._dot_y = self._anim_start_y + (self._target_y - self._anim_start_y) * self._anim_progress

        if t >= 1.0:
            self._anim_timer.stop()
            self._dot_x = self._target_x
            self._dot_y = self._target_y

        self.update()

    @staticmethod
    def _ease_out(t: float) -> float:
        return 1.0 - (1.0 - t) ** 3

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        ox, oy, side, _ = self._chart_rect()
        half = side / 2.0

        # ── Rounded clip ──────────────────────────────────────────
        clip_path = QPainterPath()
        clip_path.addRoundedRect(ox, oy, side, side, 6, 6)
        painter.setClipPath(clip_path)

        # ── Flat quadrant fills ───────────────────────────────────
        quads = [
            ("TENSE", ox, oy, half, half),
            ("VIGOROUS", ox + half, oy, half, half),
            ("MELANCHOLY", ox, oy + half, half, half),
            ("CALM", ox + half, oy + half, half, half),
        ]

        for name, qx, qy, qw, qh in quads:
            is_rec = (self._confidence >= _CONFIDENCE_THRESHOLD and self._quadrant == name)
            fill = _QUADRANT_ACTIVE[name] if is_rec else _QUADRANT_COLORS[name]
            painter.fillRect(int(qx), int(qy), int(qw), int(qh), QColor(fill))

            # Bilingual label
            cn, en = _QUADRANT_LABELS[name]
            fg = _QUADRANT_FG[name] if is_rec else "#5F6368"

            # Chinese — larger, top
            cn_font = QFont()
            cn_font.setPixelSize(13 if is_rec else 12)
            cn_font.setWeight(QFont.Weight.DemiBold if is_rec else QFont.Weight.Medium)
            painter.setFont(cn_font)
            painter.setPen(QColor(fg))
            painter.drawText(int(qx), int(qy) - 1, int(qw), int(qh // 2 + 3),
                             Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter, cn)

            # English — smaller, bottom
            en_font = QFont()
            en_font.setPixelSize(8)
            en_font.setWeight(QFont.Weight.Normal if is_rec else QFont.Weight.Light)
            if not is_rec:
                en_font.setWeight(QFont.Weight.Light)
            painter.setFont(en_font)
            painter.setPen(QColor("#9CA3AF"))
            painter.drawText(int(qx), int(qy + qh // 2), int(qw), int(qh // 2 - 1),
                             Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter, en)

            # Highlight border on recommended
            if is_rec:
                border_pen = QPen(QColor(_QUADRANT_FG[name]), 1.5)
                painter.setPen(border_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(int(qx) + 1, int(qy) + 1, int(qw) - 2, int(qh) - 2)

        # ── Crosshair ─────────────────────────────────────────────
        cross_pen = QPen(QColor("#D1D5DB"), 0.8)
        painter.setPen(cross_pen)
        painter.drawLine(int(ox + half), int(oy), int(ox + half), int(oy + side))
        painter.drawLine(int(ox), int(oy + half), int(ox + side), int(oy + half))

        # ── Center dot ────────────────────────────────────────────
        if self._dot_visible:
            cx = self._dot_x
            cy = self._dot_y
            dot_color = QColor("#FB8C00") if self._boundary_flash else QColor("#1A73E8")
            if self._boundary_flash:
                self._boundary_flash = False

            glow = QColor(dot_color.red(), dot_color.green(), dot_color.blue(), 50)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(glow)
            painter.drawEllipse(QPointF(cx, cy), _DOT_SIZE * 0.9, _DOT_SIZE * 0.9)

            painter.setPen(QPen(QColor("#FFFFFF"), _DOT_BORDER))
            painter.setBrush(dot_color)
            painter.drawEllipse(QPointF(cx, cy), _DOT_SIZE / 2, _DOT_SIZE / 2)

        # ── Idle hint ─────────────────────────────────────────────
        if not self._dot_visible:
            hint_font = QFont()
            hint_font.setPixelSize(12)
            hint_font.setWeight(QFont.Weight.Normal)
            painter.setFont(hint_font)
            painter.setPen(QColor("#9CA3AF"))
            painter.drawText(int(ox), int(oy), int(side), int(side - 8),
                             Qt.AlignmentFlag.AlignCenter, "等待音频\nAwaiting Audio")

        painter.setClipping(False)

        # ── Chart border ──────────────────────────────────────────
        border_pen = QPen(QColor("#E5E7EB"), 1)
        painter.setPen(border_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(ox, oy, side, side, 6, 6)

        painter.end()
