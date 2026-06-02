"""
Playlist grid — 5-column (volume label + 4 mood tags) button grid built from config.
"""

from functools import partial

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QGridLayout, QLabel, QPushButton

from gui.theme import PLAYLIST_BTN_QSS, PLAYLIST_BTN_HIGHLIGHT_QSS

TAG_ORDER = ["VIGOROUS", "TENSE", "MELANCHOLY", "CALM"]
TAG_LABELS = ["活力", "紧张", "忧郁", "平静"]


class PlaylistGrid(QWidget):
    """5-column playist button grid driven by PlaylistConfig data."""

    classify_requested = None  # Signal replaced by on_classify callback

    def __init__(self, moods: list[dict], volumes: list[str],
                 on_classify: callable, parent: QWidget | None = None):
        """
        Args:
            moods: result of config.get_all_moods_flat()
            volumes: ordered list of volume names
            on_classify: callable(playlist_name, volume_name)
        """
        super().__init__(parent)
        self._buttons: list[QPushButton] = []
        self._moods = moods
        self._volumes = volumes

        grid = QGridLayout(self)
        grid.setSpacing(4)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setColumnStretch(0, 0)
        for col in range(1, 5):
            grid.setColumnStretch(col, 1)

        grid.addWidget(QLabel(""), 0, 0)
        for col, tag_label in enumerate(TAG_LABELS, start=1):
            header = QLabel(tag_label)
            header.setObjectName("tag_header")
            header.setAlignment(Qt.AlignCenter)
            grid.addWidget(header, 0, col)

        for row_idx, volume_name in enumerate(self._volumes, start=1):
            vol_label = QLabel(volume_name)
            vol_label.setObjectName("volume_label")
            vol_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            grid.addWidget(vol_label, row_idx, 0)

            vol_moods = {m["tag"]: m for m in moods if m["volume"] == volume_name}
            for col_idx, tag in enumerate(TAG_ORDER, start=1):
                if tag not in vol_moods:
                    continue
                mood_info = vol_moods[tag]
                btn = QPushButton(mood_info["mood_name"])
                btn.setObjectName("playlist_btn")
                btn.clicked.connect(
                    partial(on_classify, mood_info["playlist"], volume_name)
                )
                self._buttons.append(btn)
                grid.addWidget(btn, row_idx, col_idx)

        grid.setRowStretch(len(self._volumes) + 1, 1)

        self.set_buttons_active(False)
        self._clear_highlight()

    def set_buttons_active(self, active: bool) -> None:
        for btn in self._buttons:
            btn.setEnabled(active)

    def disable_missing_playlists(self, missing_playlist_names: set[str]) -> None:
        """Disable buttons whose playlist template is missing."""
        idx = 0
        for volume_name in self._volumes:
            vol_moods = {m["tag"]: m for m in self._moods
                         if m["volume"] == volume_name}
            for tag in TAG_ORDER:
                if tag not in vol_moods:
                    continue
                if idx < len(self._buttons):
                    if vol_moods[tag]["playlist"] in missing_playlist_names:
                        self._buttons[idx].setEnabled(False)
                idx += 1

    def highlight_quadrant(self, quadrant: str) -> None:
        """Highlight buttons matching the recommended mood quadrant."""
        idx = 0
        for volume_name in self._volumes:
            vol_moods = {m["tag"]: m for m in self._moods
                         if m["volume"] == volume_name}
            for tag in TAG_ORDER:
                if tag not in vol_moods:
                    continue
                if idx < len(self._buttons):
                    btn = self._buttons[idx]
                    if tag == quadrant:
                        btn.setStyleSheet(PLAYLIST_BTN_HIGHLIGHT_QSS)
                    else:
                        btn.setStyleSheet(PLAYLIST_BTN_QSS)
                idx += 1

    def _clear_highlight(self) -> None:
        """Reset all buttons to default style."""
        for btn in self._buttons:
            btn.setStyleSheet(PLAYLIST_BTN_QSS)

    def clear_highlight(self) -> None:
        self._clear_highlight()
