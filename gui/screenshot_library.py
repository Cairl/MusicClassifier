"""Screenshot library — clean vertical list of all templates with status indicators."""

from collections.abc import Callable

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget,
)
from PySide6.QtCore import Qt, QRect

from core.template_library import TemplateLibrary
from core.playlist_config import PlaylistConfig
from core.screen_capture import ScreenCapture
from gui.screenshot_overlay import ScreenshotOverlay
from gui.countdown_overlay import CountdownOverlay

_BG = "#fafafa"
_SURFACE = "#ffffff"
_ON_SURFACE = "#202124"
_SECONDARY = "#5f6368"
_SUBTLE = "#80868b"
_MUTED = "#9aa0a6"
_SEPARATOR = "#e8eaed"
_ACCENT = "#1a73e8"
_OK_GREEN = "#34a853"
_MISSING_RED = "#ea4335"


class _TemplateItem(QWidget):
    """A single row in the screenshot library list."""

    def __init__(self, name: str, label: str, category: str,
                 has_image: bool,
                 on_capture: Callable[[str], None] | None = None,
                 on_delete: Callable[[str], None] | None = None,
                 parent=None):
        super().__init__(parent)
        self._name = name
        self._has_image = has_image

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 3, 8, 3)
        layout.setSpacing(6)

        # Status dot
        dot = QLabel()
        dot.setFixedSize(8, 8)
        dot.setStyleSheet(
            f"background-color: {_OK_GREEN if has_image else _MISSING_RED};"
            f"border-radius: 4px;"
        )
        layout.addWidget(dot, 0, Qt.AlignVCenter)

        # Label
        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"color: {_ON_SURFACE}; font-size: 12px;"
            + (f" font-weight: 400;" if has_image else f" font-weight: 600;")
        )
        layout.addWidget(lbl, 1)

        # Delete button (left of capture, always visible when has_image and on_delete)
        if has_image and on_delete:
            del_btn = QPushButton("删除")
            del_btn.setFixedHeight(24)
            del_btn.setStyleSheet(
                "QPushButton {"
                f"  background-color: transparent; color: {_MUTED}; border: none;"
                "  border-radius: 6px; padding: 2px 8px; font-size: 11px; font-weight: 400;"
                "}"
                f"QPushButton:hover {{ background-color: #fce4ec; color: {_MISSING_RED}; }}"
            )
            del_btn.clicked.connect(lambda: on_delete(self._name))
            layout.addWidget(del_btn)

        # Capture / Recapture button (right side)
        if on_capture:
            btn = QPushButton("重截" if has_image else "截取")
            btn.setFixedHeight(24)
            if has_image:
                btn.setStyleSheet(
                    "QPushButton {"
                    f"  background-color: {_SEPARATOR}; color: {_ON_SURFACE}; border: none;"
                    "  border-radius: 6px; padding: 2px 10px; font-size: 11px; font-weight: 500;"
                    "}"
                    f"QPushButton:hover {{ background-color: #dadce0; }}"
                )
            else:
                btn.setStyleSheet(
                    "QPushButton {"
                    f"  background-color: {_ACCENT}; color: #ffffff; border: none;"
                    "  border-radius: 6px; padding: 2px 10px; font-size: 11px; font-weight: 600;"
                    "}"
                    f"QPushButton:hover {{ background-color: #1557b0; }}"
                )
            btn.clicked.connect(lambda: on_capture(self._name))
            layout.addWidget(btn)


class ScreenshotLibrary(QDialog):
    """Dialog showing all templates in a vertical list with status indicators."""

    def __init__(self, template_lib: TemplateLibrary,
                 config: PlaylistConfig,
                 screen_capture: ScreenCapture | None = None,
                 parent=None):
        super().__init__(parent)
        self._template_lib = template_lib
        self._config = config
        self._screen_capture = screen_capture
        self._items: list[_TemplateItem] = []

        self.setWindowTitle("截图库")
        self.setMinimumSize(380, 400)
        self.setStyleSheet(f"QDialog {{ background-color: {_BG}; }}")
        self._init_ui()
        self._populate()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header bar
        header_bar = QWidget()
        header_bar.setStyleSheet(f"background-color: {_SURFACE};")
        header_layout = QVBoxLayout(header_bar)
        header_layout.setContentsMargins(12, 12, 12, 10)
        header_layout.setSpacing(6)

        self._summary = QLabel()
        self._summary.setStyleSheet(
            f"font-size: 12px; font-weight: 500; padding: 6px 10px; "
            f"border-radius: 6px;"
        )
        header_layout.addWidget(self._summary)
        layout.addWidget(header_bar)

        # Separator
        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {_SEPARATOR};")
        layout.addWidget(sep)

        # Scrollable list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { width: 4px; background: transparent; }"
            "QScrollBar::handle:vertical { background: #dadce0; border-radius: 2px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )

        self._list_widget = QWidget()
        self._list_widget.setStyleSheet(f"background-color: {_BG};")
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(8, 6, 8, 6)
        self._list_layout.setSpacing(1)
        self._list_layout.addStretch()

        scroll.setWidget(self._list_widget)
        layout.addWidget(scroll, 1)

        # Close button bar
        btn_bar = QWidget()
        btn_bar.setStyleSheet(f"background-color: {_SURFACE};")
        btn_layout = QHBoxLayout(btn_bar)
        btn_layout.setContentsMargins(12, 8, 12, 10)
        btn_layout.addStretch()

        close_btn = QPushButton("关闭")
        close_btn.setStyleSheet(
            "QPushButton {"
            f"  background-color: {_SEPARATOR}; color: {_ON_SURFACE}; border: none;"
            "  border-radius: 8px; padding: 8px 16px; font-size: 12px; font-weight: 500;"
            "}"
            "QPushButton:hover { background-color: #dadce0; }"
        )
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addWidget(btn_bar)

    def _build_items(self) -> list[tuple[str, str, str, bool]]:
        existing = set(self._template_lib.list_all_names())

        items: list[tuple[str, str, str, bool]] = []

        # UI templates
        items.append(("ui/more_button", "更多", "UI 素材",
                       "ui/more_button" in existing))
        items.append(("ui/add_to_playlist", "添加到播放列表", "UI 素材",
                       "ui/add_to_playlist" in existing))

        # Volume templates
        for vol_name in self._config.get_volumes():
            name = f"volumes/{vol_name}"
            items.append((name, f"卷名: {vol_name}", "卷名素材", name in existing))

        # Playlist templates
        for mood in self._config.get_all_moods_flat():
            name = f"playlists/{mood['playlist']}"
            items.append((name, f"歌单: {mood['playlist']} ({mood['volume']})",
                          "歌单素材", name in existing))

        return items

    def _populate(self):
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        self._items.clear()
        entries = self._build_items()

        groups: dict[str, list] = {}
        for name, label, cat, has in entries:
            groups.setdefault(cat, []).append((name, label, cat, has))

        cat_order = ["UI 素材", "卷名素材", "歌单素材"]
        total = 0
        existing_count = 0

        first = True
        for cat in cat_order:
            if cat not in groups:
                continue

            if not first:
                sep = QWidget()
                sep.setFixedHeight(4)
                self._list_layout.insertWidget(self._list_layout.count() - 1, sep)
            first = False

            header = QLabel(cat)
            header.setStyleSheet(
                f"font-size: 10px; font-weight: 700; color: {_MUTED}; "
                f"padding: 6px 12px 2px 12px; letter-spacing: 0.5px;"
            )
            self._list_layout.insertWidget(self._list_layout.count() - 1, header)

            for name, label, c, has in groups[cat]:
                total += 1
                if has:
                    existing_count += 1
                item = _TemplateItem(
                    name, label, c, has,
                    on_capture=self._on_capture_single,
                    on_delete=self._on_delete_template,
                )
                self._items.append(item)
                self._list_layout.insertWidget(self._list_layout.count() - 1, item)

        missing = total - existing_count
        self._summary.setText(
            f"已就绪 {existing_count} / {total} 项"
            + (f"  ·  缺失 {missing} 项" if missing else "  ·  全部完成")
        )
        if missing:
            self._summary.setStyleSheet(
                f"font-size: 11px; font-weight: 500; padding: 4px 8px; "
                f"border-radius: 6px; background-color: #fce8e6; color: #c5221f;"
            )
        else:
            self._summary.setStyleSheet(
                f"font-size: 11px; font-weight: 500; padding: 4px 8px; "
                f"border-radius: 6px; background-color: #e6f4ea; color: #137333;"
            )

    def _on_delete_template(self, name: str):
        """Delete a template file and refresh."""
        self._template_lib.delete_template(name)
        self._populate()

    def _on_capture_single(self, name: str):
        """Capture or recapture a single template with 5-second countdown."""
        if self._screen_capture is None:
            return

        import sys

        # Make library invisible but keep it modal (opacity instead of hide)
        self.setWindowOpacity(0)

        if not CountdownOverlay.countdown(5, self):
            self.setWindowOpacity(1)
            return

        # Take screenshot — pyautogui returns RGB, keep as RGB throughout
        screenshot = self._screen_capture.capture_full_screen(delay_ms=500)
        if screenshot is None:
            self.setWindowOpacity(1)
            print("[ERROR] 截图失败", file=sys.stderr, flush=True)
            return

        # Show region selection overlay (library invisible underneath)
        overlay = ScreenshotOverlay(screenshot, self)
        result_rect: QRect | None = None

        def on_selected(rect: QRect):
            nonlocal result_rect
            result_rect = rect

        overlay.region_selected.connect(on_selected)
        overlay.exec()

        if result_rect is None:
            self.setWindowOpacity(1)
            return

        # Crop from the first screenshot using DPR-scaled overlay coordinates
        x1, y1 = result_rect.x(), result_rect.y()
        x2, y2 = x1 + result_rect.width(), y1 + result_rect.height()
        x1, x2 = max(0, x1), min(screenshot.shape[1], x2)
        y1, y2 = max(0, y1), min(screenshot.shape[0], y2)
        cropped = screenshot[y1:y2, x1:x2]
        self.setWindowOpacity(1)
        if cropped.size == 0:
            return

        self._template_lib.save_template(name, cropped)
        # Save region position for fixed-position elements
        window_rect = self._screen_capture._window_rect
        if window_rect:
            self._template_lib.save_region(
                name, x1, y1, x2 - x1, y2 - y1,
                (window_rect[0], window_rect[1]),
            )
        self._populate()
