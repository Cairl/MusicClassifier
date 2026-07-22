"""Calibration popover — 3x3 valence-arousal grid for user correction."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialog, QGridLayout, QPushButton, QVBoxLayout, QLabel

_CELL_VALUE = {-1: -2 / 3, 0: 0.0, 1: 2 / 3}
_ROW_LABELS = ["高能量", "中等", "低能量"]
_COL_LABELS = ["负面", "中性", "愉悦"]


class CalibrationPopover(QDialog):
    corrected = Signal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("校正当前情绪")
        self.setModal(True)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("这首歌实际听起来是什么感觉？"))
        grid = QGridLayout()
        grid.setSpacing(4)
        for row in range(3):
            for col in range(3):
                label = f"{_ROW_LABELS[row]}\n{_COL_LABELS[col]}"
                btn = QPushButton(label)
                btn.setFixedSize(72, 48)
                btn.clicked.connect(
                    lambda checked=False, r=row, c=col: self._emit_cell(r, c))
                grid.addWidget(btn, row, col)
        layout.addLayout(grid)

    def _emit_cell(self, row: int, col: int) -> None:
        arousal = _CELL_VALUE[1 - row]
        valence = _CELL_VALUE[col - 1]
        self.corrected.emit(valence, arousal)
        self.accept()
