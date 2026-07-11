"""Real-time audio frequency spectrum bar with peak-hold visualization."""

import numpy as np
from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QPainterPath


_NUM_BANDS = 16
_FFT_SIZE = 4096
_BAR_GAP = 2
_BAR_RX = 2
_PEAK_FALL = 0.04
_PEAK_SIZE = 2
_UPDATE_INTERVAL_MS = 66


def _log_band_edges(n_bands: int, fft_size: int, sr: int = 48000):
    low = 20.0
    high = sr / 2
    edges = np.logspace(np.log10(low), np.log10(high), n_bands + 1)
    bin_edges = np.round(edges / sr * fft_size).astype(int)
    bin_edges = np.clip(bin_edges, 0, fft_size // 2)
    result = []
    prev = bin_edges[0]
    for i in range(1, len(bin_edges)):
        cur = bin_edges[i]
        if cur <= prev:
            cur = prev + 1
        result.append((prev, cur))
        prev = cur
    return result


_BANDS = _log_band_edges(_NUM_BANDS, _FFT_SIZE)

_BG = "#ffffff"
_BAR_COLOR = QColor("#90CAF9")
_BAR_ACTIVE = QColor("#1A73E8")
_PEAK_COLOR = QColor("#1565C0")
_GRID_COLOR = QColor("#E8EAED")


class SpectrumBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("spectrum_bar")
        self.setFixedHeight(32)
        self._levels = np.zeros(_NUM_BANDS, dtype=np.float32)
        self._peaks = np.zeros(_NUM_BANDS, dtype=np.float32)
        self._active = False
        self._timer = QTimer(self)
        self._timer.setInterval(_UPDATE_INTERVAL_MS)

    def set_update_callback(self, callback):
        self._timer.timeout.connect(callback)

    def start(self):
        self._active = True
        self._timer.start()

    def stop(self):
        self._active = False
        self._timer.stop()
        self._levels = np.zeros(_NUM_BANDS, dtype=np.float32)
        self._peaks = np.zeros(_NUM_BANDS, dtype=np.float32)
        self.update()

    def update_levels(self, levels: np.ndarray):
        clamped = np.clip(levels, 0.0, 1.0).astype(np.float32)
        if len(clamped) >= _NUM_BANDS:
            clamped = clamped[:_NUM_BANDS]
        else:
            padded = np.zeros(_NUM_BANDS, dtype=np.float32)
            padded[:len(clamped)] = clamped
            clamped = padded
        self._levels = clamped
        mask = clamped > self._peaks
        self._peaks[mask] = clamped[mask]
        self._peaks = np.maximum(self._peaks - _PEAK_FALL, 0.0)
        self.update()

    def compute_fft(self, audio: np.ndarray) -> np.ndarray:
        if audio is None or len(audio) < _FFT_SIZE:
            return np.zeros(_NUM_BANDS, dtype=np.float32)
        window = np.hanning(len(audio))
        spectrum = np.abs(np.fft.rfft(audio * window, n=_FFT_SIZE))
        levels = np.zeros(_NUM_BANDS, dtype=np.float32)
        for i, (lo, hi) in enumerate(_BANDS):
            if hi > lo and lo < len(spectrum):
                seg = spectrum[lo:min(hi, len(spectrum))]
                levels[i] = np.mean(seg) if len(seg) > 0 else 0.0
        max_val = np.max(levels)
        if max_val > 1e-10:
            levels = levels / max_val
            levels = np.power(levels, 0.4)
        return np.clip(levels, 0.0, 1.0)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        bar_w = (w - (_NUM_BANDS + 1) * _BAR_GAP) / _NUM_BANDS

        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, w, h), 6, 6)
        painter.setClipPath(path)
        painter.fillRect(0, 0, w, h, QColor(_BG))

        for i in range(_NUM_BANDS):
            x = _BAR_GAP + i * (bar_w + _BAR_GAP)
            level = float(self._levels[i])
            bar_h = level * (h - 4)
            if bar_h < 2:
                bar_h = 2
            y = h - 2 - bar_h

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(_BAR_ACTIVE if self._active else _BAR_COLOR)
            painter.drawRoundedRect(QRectF(x, y, bar_w, bar_h),
                                    _BAR_RX, _BAR_RX)

            peak = float(self._peaks[i])
            if peak > 0.01:
                px = x + bar_w / 2 - _PEAK_SIZE
                py = h - 2 - peak * (h - 4) - _PEAK_SIZE
                painter.setPen(QPen(_PEAK_COLOR, 1.2))
                painter.setBrush(_PEAK_COLOR)
                painter.drawRoundedRect(
                    QRectF(px, py, _PEAK_SIZE * 2, _PEAK_SIZE * 2),
                    1, 1)

        if not self._active:
            painter.setClipping(False)
            hint = QFont()
            hint.setPixelSize(10)
            hint.setWeight(QFont.Weight.Bold)
            painter.setFont(hint)
            painter.setPen(QColor("#9CA3AF"))
            painter.drawText(QRectF(0, 0, w, h),
                             Qt.AlignmentFlag.AlignCenter,
                             "频谱 Idle")

        painter.end()
