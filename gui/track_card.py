"""Track info card — displays song name, artist, and album on separate lines."""

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

        self._artist_label = QLabel("")
        self._artist_label.setObjectName("track_subtitle")
        layout.addWidget(self._artist_label)

        self._album_label = QLabel("")
        self._album_label.setObjectName("track_subtitle")
        layout.addWidget(self._album_label)

    def set_track(self, song_name: str, artist: str = "", album: str = "") -> None:
        self._name_label.setText(song_name or "未知歌曲")
        self._artist_label.setText(artist if artist else "")
        self._album_label.setText(album if album else "")

    def reset(self) -> None:
        self._name_label.setText("等待识别...")
        self._artist_label.setText("")
        self._album_label.setText("")
