from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QLinearGradient, QFont


_QUADRANT_COLORS = {
    "CALM": ("#E8F5E9", "#C8E6C9"),
    "VIGOROUS": ("#FFF3E0", "#FFE0B2"),
    "MELANCHOLY": ("#ECEFF1", "#CFD8DC"),
    "TENSE": ("#FCE4EC", "#F8BBD0"),
}

_QUADRANT_LABELS = {
    "CALM": ("平静", "CALM"),
    "VIGOROUS": ("活力", "VIGOROUS"),
    "MELANCHOLY": ("忧郁", "MELANCHOLY"),
    "TENSE": ("紧张", "TENSE"),
}

_CONFIDENCE_THRESHOLD = 0.6
_DOT_SIZE = 12
_DOT_BORDER = 4


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
        self.setFixedHeight(160)

    @property
    def recommended_quadrant(self) -> str | None:
        if self._confidence >= _CONFIDENCE_THRESHOLD and self._quadrant:
            return self._quadrant
        return None

    def update_mood(self, arousal: float, valence: float, quadrant: str, confidence: float) -> None:
        self._arousal = arousal
        self._valence = valence
        self._quadrant = quadrant
        self._confidence = confidence
        self._dot_visible = True
        self._dot_x, self._dot_y = self._dot_pixel_pos()
        self.update()

    def reset(self) -> None:
        self._arousal = 0.0
        self._valence = 0.0
        self._quadrant = ""
        self._confidence = 0.0
        self._dot_visible = False
        self.update()

    def _dot_pixel_pos(self) -> tuple[float, float]:
        w = self.width()
        h = self.height()
        x = (self._valence + 1.0) / 2.0 * w
        y = (1.0 - (self._arousal + 1.0) / 2.0) * h
        return x, y

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        half_w = w / 2
        half_h = h / 2

        quadrants = [
            ("CALM", 0, 0, half_w, half_h),
            ("VIGOROUS", half_w, 0, half_w, half_h),
            ("MELANCHOLY", 0, half_h, half_w, half_h),
            ("TENSE", half_w, half_h, half_w, half_h),
        ]

        for name, qx, qy, qw, qh in quadrants:
            color_top, color_bottom = _QUADRANT_COLORS[name]
            gradient = QLinearGradient(qx, qy, qx, qy + qh)
            gradient.setColorAt(0, QColor(color_top))
            gradient.setColorAt(1, QColor(color_bottom))
            painter.fillRect(int(qx), int(qy), int(qw), int(qh), gradient)

            is_recommended = (self._confidence >= _CONFIDENCE_THRESHOLD
                              and self._quadrant == name)
            if is_recommended:
                pen = QPen(QColor("#1a73e8"), 2)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(int(qx) + 1, int(qy) + 1, int(qw) - 2, int(qh) - 2)

            cn_label, en_label = _QUADRANT_LABELS[name]
            font = QFont()
            font.setPixelSize(10)
            painter.setFont(font)
            painter.setPen(QColor("#5f6368"))
            painter.drawText(int(qx), int(qy), int(qw), int(qh),
                             Qt.AlignmentFlag.AlignCenter, f"{cn_label}\n{en_label}")

        pen = QPen(QColor("#dadce0"), 1)
        painter.setPen(pen)
        painter.drawLine(int(half_w), 0, int(half_w), h)
        painter.drawLine(0, int(half_h), w, int(half_h))

        if self._dot_visible:
            cx = self._dot_x
            cy = self._dot_y
            painter.setPen(QPen(QColor("#ffffff"), _DOT_BORDER))
            painter.setBrush(QColor("#1a73e8"))
            painter.drawEllipse(QPointF(cx, cy), _DOT_SIZE / 2, _DOT_SIZE / 2)

        painter.end()
