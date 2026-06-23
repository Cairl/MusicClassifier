"""Track info card — compact 2-line display with single-line elision."""

from PySide6.QtCore import Qt, QRect
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtGui import QFontMetrics

from gui.theme import CARD_HEIGHT


class TrackCard(QWidget):
    """Card showing currently detected track info in a compact layout."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("track_card")
        self.setFixedHeight(CARD_HEIGHT)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(2)

        self._name_label = QLabel("等待识别...")
        self._name_label.setObjectName("track_name")
        self._name_label.setWordWrap(False)
        self._name_label.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self._name_label)

        self._subtitle_label = QLabel("")
        self._subtitle_label.setObjectName("track_subtitle")
        self._subtitle_label.setWordWrap(False)
        self._subtitle_label.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self._subtitle_label)

    def _elide_text(self, label: QLabel, text: str) -> None:
        """Set text on a label, eliding if wider than available width."""
        fm = QFontMetrics(label.font())
        max_width = label.width() - 4
        if fm.horizontalAdvance(text) > max_width > 0:
            label.setText(fm.elidedText(text, Qt.TextElideMode.ElideRight, max_width))
        else:
            label.setText(text)

    def _update_labels(self) -> None:
        """Reapply elision to current texts (call after resize)."""
        self._name_label.setText(self._raw_name or "等待识别...")
        self._subtitle_label.setText(self._raw_subtitle)
        # Re-elide after setting raw text
        self._elide_text(self._name_label, self._name_label.text())
        self._elide_text(self._subtitle_label, self._subtitle_label.text())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_labels()

    def set_track(self, song_name: str, artist: str = "", album: str = "") -> None:
        self._raw_name = song_name or "未知歌曲"
        parts: list[str] = []
        if artist:
            parts.append(artist)
        if album and album != artist:
            parts.append(album)
        self._raw_subtitle = " \u00b7 ".join(parts) if parts else ""
        self._update_labels()

    def reset(self) -> None:
        self._raw_name = "等待识别..."
        self._raw_subtitle = ""
        self._update_labels()
