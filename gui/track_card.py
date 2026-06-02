"""Track info card — displays current song name and album. Clean, no redundant info."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

from gui.theme import CARD_HEIGHT


class TrackCard(QWidget):
    """Card showing the currently detected track info."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("track_card")
        self.setFixedHeight(CARD_HEIGHT)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(0)

        self._name_label = QLabel("等待识别...")
        self._name_label.setObjectName("track_name")
        layout.addWidget(self._name_label)

        self._album_label = QLabel("")
        self._album_label.setObjectName("track_subtitle")
        layout.addWidget(self._album_label)

    def set_track(self, name: str, album: str) -> None:
        self._name_label.setText(name)
        self._album_label.setText(album if album else "")

    def reset(self) -> None:
        self._name_label.setText("等待识别...")
        self._album_label.setText("")
