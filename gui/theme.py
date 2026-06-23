"""Design system tokens for MusicClassifier.
Material Design 3 light gray palette with mood accent colors."""

# ── Color Palette ──────────────────────────────────────────────────
COLOR_BG = "#fafafa"
COLOR_SURFACE = "#ffffff"
COLOR_ON_SURFACE = "#202124"
COLOR_SECONDARY = "#5f6368"
COLOR_SUBTLE = "#80868b"
COLOR_MUTED = "#9aa0a6"

COLOR_SIDEBAR_BG = "#ffffff"
COLOR_SEPARATOR = "#e8eaed"

COLOR_CARD_BG = "#ffffff"

COLOR_BTN_FILL = "#e8eaed"
COLOR_BTN_FILL_HOVER = "#dadce0"
COLOR_BTN_FILL_PRESSED = "#c4c7c9"
COLOR_BTN_FILL_DISABLED = "#f1f3f4"

COLOR_BTN_TEXT = "#202124"
COLOR_BTN_TEXT_DISABLED = "#9aa0a6"

COLOR_ACCENT = "#1a73e8"
COLOR_ACCENT_BG = "#e8f0fe"
COLOR_ACCENT_BG_HOVER = "#d2e3fc"
COLOR_ACCENT_BG_PRESSED = "#aecbfa"

COLOR_DOT_DEFAULT = "#1a73e8"
COLOR_DOT_BOUNDARY = "#fb8c00"

# ── Mood Colors ────────────────────────────────────────────────────
MOOD_COLORS = {
    "VIGOROUS": {"fg": "#e65100", "bg": "#fff3e0", "border": "#ffe0b2"},
    "TENSE":    {"fg": "#c62828", "bg": "#fce4ec", "border": "#f8bbd0"},
    "MELANCHOLY": {"fg": "#37474f", "bg": "#eceff1", "border": "#cfd8dc"},
    "CALM":     {"fg": "#2e7d32", "bg": "#e8f5e9", "border": "#c8e6c9"},
}

MOOD_LABELS = {
    "VIGOROUS": "活力",
    "TENSE": "紧张",
    "MELANCHOLY": "忧郁",
    "CALM": "平静",
}

# ── Typography ─────────────────────────────────────────────────────
FONT_SIZE_XXS = "7px"
FONT_SIZE_XS = "10px"
FONT_SIZE_SM = "11px"
FONT_SIZE_MD = "12px"
FONT_SIZE_LG = "14px"
FONT_SIZE_TITLE = "15px"

FONT_WEIGHT_NORMAL = "700"
FONT_WEIGHT_MEDIUM = "700"
FONT_WEIGHT_SEMIBOLD = "700"
FONT_WEIGHT_BOLD = "700"

# ── Spacing ────────────────────────────────────────────────────────
SPACING_XXS = 2
SPACING_XS = 4
SPACING_SM = 6
SPACING_MD = 8
SPACING_LG = 10

# ── Sizing ─────────────────────────────────────────────────────────
SIDEBAR_WIDTH = 64
SIDEBAR_BUTTON_SIZE = 44
SIDEBAR_ICON_SIZE = 28

CARD_HEIGHT = 68

PLAYLIST_BTN_MIN_HEIGHT = 30
PLAYLIST_BTN_PADDING = "5px 4px"

# ── Border Radius (squircle-approximated, ~0.7x of control height) ──
RADIUS_SM = "14px"
RADIUS_MD = "24px"
RADIUS_CIRCLE = "22px"
RADIUS_PILL = "15px"

# ── Shadow (QSS drop-shadow) ───────────────────────────────────────
CARD_SHADOW = "box-shadow: 0 1px 3px rgba(0,0,0,0.08);"

# ── Shared QSS Bits ────────────────────────────────────────────────

SIDEBAR_BUTTON_QSS = f"""
    QPushButton {{
        background-color: transparent;
        border: none;
        border-radius: {RADIUS_CIRCLE};
        padding: 0px;
    }}
    QPushButton:hover {{
        background-color: {COLOR_SEPARATOR};
    }}
    QPushButton:pressed {{
        background-color: {COLOR_BTN_FILL_PRESSED};
    }}
"""

SIDEBAR_BUTTON_ACTIVE_QSS = f"""
    QPushButton {{
        background-color: {COLOR_SEPARATOR};
        border: none;
        border-radius: {RADIUS_CIRCLE};
        padding: 0px;
    }}
    QPushButton:hover {{
        background-color: {COLOR_BTN_FILL_HOVER};
    }}
    QPushButton:pressed {{
        background-color: {COLOR_BTN_FILL_PRESSED};
    }}
"""

PLAYLIST_BTN_QSS = f"""
    QPushButton {{
        background-color: {COLOR_BTN_FILL};
        color: {COLOR_BTN_TEXT};
        border: none;
        border-radius: {RADIUS_SM};
        padding: {PLAYLIST_BTN_PADDING};
        font-size: {FONT_SIZE_MD};
        min-height: {PLAYLIST_BTN_MIN_HEIGHT}px;
    }}
    QPushButton:hover {{
        background-color: {COLOR_BTN_FILL_HOVER};
    }}
    QPushButton:pressed {{
        background-color: {COLOR_BTN_FILL_PRESSED};
    }}
    QPushButton:disabled {{
        background-color: {COLOR_BTN_FILL_DISABLED};
        color: {COLOR_BTN_TEXT_DISABLED};
    }}
"""

PLAYLIST_BTN_HIGHLIGHT_QSS = f"""
    QPushButton {{
        background-color: {COLOR_ACCENT_BG};
        color: {COLOR_ACCENT};
        border: 2px solid {COLOR_ACCENT};
        border-radius: {RADIUS_SM};
        padding: {PLAYLIST_BTN_PADDING};
        font-size: {FONT_SIZE_MD};
        min-height: {PLAYLIST_BTN_MIN_HEIGHT}px;
        font-weight: {FONT_WEIGHT_SEMIBOLD};
    }}
    QPushButton:hover {{
        background-color: {COLOR_ACCENT_BG_HOVER};
    }}
    QPushButton:pressed {{
        background-color: {COLOR_ACCENT_BG_PRESSED};
    }}
"""

MAIN_QSS = f"""
QMainWindow {{
    background: {COLOR_BG};
}}
QWidget#outer {{
    background: {COLOR_BG};
}}
QWidget#sidebar {{
    background: {COLOR_SIDEBAR_BG};
}}
QWidget#track_card {{
    background: {COLOR_CARD_BG};
    border: none;
    border-radius: {RADIUS_MD};
}}
QLabel#track_name {{
    font-size: {FONT_SIZE_TITLE};
    font-weight: 600;
    color: {COLOR_ON_SURFACE};
    line-height: 1.3;
}}
QLabel#track_subtitle {{
    font-size: {FONT_SIZE_SM};
    color: {COLOR_SUBTLE};
    line-height: 1.2;
}}
QLabel#volume_tag {{
    font-size: {FONT_SIZE_SM};
    color: {COLOR_SECONDARY};
    font-weight: {FONT_WEIGHT_SEMIBOLD};
    letter-spacing: 0.5px;
}}
QLabel#tag_header {{
    font-size: {FONT_SIZE_XS};
    font-weight: {FONT_WEIGHT_SEMIBOLD};
    color: {COLOR_SECONDARY};
    letter-spacing: 1px;
}}
QLabel#volume_label {{
    font-size: {FONT_SIZE_MD};
    font-weight: {FONT_WEIGHT_SEMIBOLD};
    color: {COLOR_ON_SURFACE};
}}
QLabel#mood_status {{
    font-size: {FONT_SIZE_SM};
    font-weight: {FONT_WEIGHT_MEDIUM};
    padding: 3px 8px;
    border-radius: {RADIUS_SM};
    background-color: {COLOR_SEPARATOR};
    color: {COLOR_SECONDARY};
}}
QLabel#mood_status[active="true"] {{
    background-color: {COLOR_ACCENT_BG};
    color: {COLOR_ACCENT};
    font-weight: {FONT_WEIGHT_SEMIBOLD};
}}
"""

CAPTURE_WIZARD_QSS = f"""
    QDialog {{
        background-color: {COLOR_BG};
    }}
    QLabel {{
        color: {COLOR_ON_SURFACE};
    }}
    QProgressBar {{
        border: none;
        border-radius: {SPACING_XS}px;
        background-color: {COLOR_SEPARATOR};
        text-align: center;
        color: {COLOR_ON_SURFACE};
    }}
    QProgressBar::chunk {{
        background-color: {COLOR_SECONDARY};
        border-radius: {SPACING_XS}px;
    }}
"""
