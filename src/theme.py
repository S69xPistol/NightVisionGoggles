"""
Colours, fonts and the Qt stylesheet. Values come from the approved mockup.
`T` is the active palette; it is updated in place when the theme changes so
custom-painted widgets always read the current colours.
"""
from PySide6.QtGui import QFontDatabase

ACCENT = "#f5a524"
ACCENT_HOVER = "#ffb84a"
ON_ACCENT = "#16181d"
DANGER = "#d13b3b"
DANGER_HOVER = "#e04848"
DANGER_TEXT = "#ff5c5c"
CLOSE_HOVER = "#c42b1c"
OK_GREEN = "#3fbf6e"
CHANNEL_COLORS = {"red_scale": "#ff6b6b", "green_scale": "#3fbf6e", "blue_scale": "#4d8fff"}

THEMES = {
    "dark": {"bg": "#16181d", "surface": "#1d2026", "hover": "#22252c", "border": "#2c2f38",
             "border2": "#3a3e49", "text": "#eceef2", "text2": "#c3c7d1", "muted": "#a3a8b5",
             "faint": "#8d92a0", "input": "#101216", "track": "#2c2f38", "disabled": "#5d626e",
             "accent_text": ACCENT, "off_dot": "#4a4e5a", "accent_tint": "#2e2618",
             "danger_tint": "#3a2224", "overlay": "rgba(5, 6, 8, 150)"},
    "light": {"bg": "#f5f6f8", "surface": "#ffffff", "hover": "#e8eaee", "border": "#dde0e6",
              "border2": "#c9cdd5", "text": "#16181d", "text2": "#3a3e49", "muted": "#5d626e",
              "faint": "#6b7080", "input": "#ffffff", "track": "#dde0e6", "disabled": "#9aa0ab",
              "accent_text": "#8a5200", "off_dot": "#b5bac4", "accent_tint": "#fdecd0",
              "danger_tint": "#fbe3e3", "overlay": "rgba(20, 22, 28, 90)"},
}

T = dict(THEMES["dark"])
FONTS = {"ui": "Segoe UI", "mono": "Consolas", "icon": "Segoe UI Symbol"}

# Segoe Fluent Icons (Windows 11) / Segoe MDL2 Assets (Windows 10) share these code points
G = {"sun": "", "palette": "", "drop": "", "keyboard": "", "monitor": "",
     "gear": "", "trash": "", "copy": "", "add": "", "lock": "",
     "min": "", "max": "", "restore": "", "close": "", "x": ""}


def init_fonts():
    families = set(QFontDatabase.families())
    FONTS["ui"] = next((f for f in ("Segoe UI Variable Text", "Segoe UI") if f in families), "Segoe UI")
    FONTS["mono"] = next((f for f in ("Cascadia Mono", "Consolas") if f in families), "Courier New")
    FONTS["icon"] = next((f for f in ("Segoe Fluent Icons", "Segoe MDL2 Assets") if f in families), "Segoe UI Symbol")


def set_theme(dark):
    T.clear()
    T.update(THEMES["dark" if dark else "light"])


def stylesheet():
    t, f = T, FONTS
    return f"""
* {{ font-family: "{f['ui']}"; font-size: 13px; color: {t['text']}; outline: none; }}
#root, #body, QScrollArea, QScrollArea > QWidget > QWidget {{ background: {t['bg']}; }}
QToolTip {{ background: {t['border']}; color: {t['text']}; border: 1px solid {t['border2']}; padding: 4px 8px; font-size: 12px; }}

/* separators */
QFrame[sep="true"] {{ background: {t['border']}; border: none; }}

/* title bar */
#titleBar {{ background: {t['bg']}; }}
#appTitle {{ font-size: 14px; font-weight: 600; }}
QLabel[mono="true"] {{ font-family: "{f['mono']}"; font-size: 11px; color: {t['muted']}; }}
QPushButton#statusPill {{ background: transparent; border: 1px solid {t['border2']}; border-radius: 13px;
    padding: 0 14px; min-width: 40px; min-height: 24px; max-height: 24px; font-size: 12px; font-weight: 600; color: {t['muted']}; }}
QPushButton#statusPill:hover {{ background: {t['hover']}; }}
QPushButton#statusPill[on="true"] {{ background: {t['accent_tint']}; border-color: {ACCENT}; color: {t['accent_text']}; }}
QPushButton[kind="caption"] {{ font-family: "{f['icon']}"; font-size: 10px; color: {t['muted']}; background: transparent;
    border: none; border-radius: 0; min-width: 46px; max-width: 46px; min-height: 44px; max-height: 44px; }}
QPushButton[kind="caption"]:hover, QPushButton[kind="caption"][hot="true"] {{ background: {t['hover']}; color: {t['text']}; }}
QPushButton[kind="caption"]#closeBtn:hover {{ background: {CLOSE_HOVER}; color: #ffffff; }}

/* generic buttons */
QPushButton, QToolButton {{ border: none; background: transparent; border-radius: 6px; }}
QPushButton[kind="glyph"], QToolButton[kind="glyph"] {{ font-family: "{f['icon']}"; color: {t['text2']}; }}
QPushButton[kind="glyph"]:hover, QToolButton[kind="glyph"]:hover {{ background: {t['hover']}; }}
QToolButton[kind="trash"] {{ font-family: "{f['icon']}"; font-size: 13px; color: {t['faint']};
    min-width: 28px; max-width: 28px; min-height: 28px; max-height: 28px; }}
QToolButton[kind="trash"]:hover {{ color: {DANGER_TEXT}; background: {t['danger_tint']}; }}
QPushButton[kind="primary"] {{ background: {ACCENT}; color: {ON_ACCENT}; font-weight: 600; padding: 0 18px; min-height: 32px; }}
QPushButton[kind="primary"]:hover {{ background: {ACCENT_HOVER}; }}
QPushButton[kind="primary"]:disabled {{ background: {t['border']}; color: {t['disabled']}; }}
QPushButton[kind="new"] {{ background: {ACCENT}; color: {ON_ACCENT}; font-size: 12px; font-weight: 600;
    padding: 0 10px 0 8px; min-height: 28px; max-height: 28px; }}
QPushButton[kind="new"]:hover {{ background: {ACCENT_HOVER}; }}
QPushButton[kind="outline"] {{ border: 1px solid {t['border2']}; padding: 0 14px; min-height: 30px; }}
QPushButton[kind="outline"]:hover {{ background: {t['hover']}; }}
QPushButton[kind="outline"]:disabled {{ color: {t['disabled']}; }}
QPushButton[kind="ghost"] {{ color: {t['text2']}; padding: 0 10px; min-height: 32px; }}
QPushButton[kind="ghost"]:hover {{ background: {t['hover']}; }}
QPushButton[kind="danger"] {{ background: {DANGER}; color: #ffffff; font-weight: 600; padding: 0 16px; min-height: 32px; }}
QPushButton[kind="danger"]:hover {{ background: {DANGER_HOVER}; }}

/* left sidebar */
QPushButton[kind="nav"] {{ text-align: left; padding: 0 10px 0 12px; min-height: 40px; max-height: 40px;
    color: {t['text2']}; font-size: 13px; }}
QPushButton[kind="nav"]:hover {{ background: {t['hover']}; }}
QPushButton[kind="nav"]:checked {{ background: {t['hover']}; color: {t['text']}; }}
QLabel[role="footer"] {{ font-size: 11px; color: {t['muted']}; }}

/* content */
#tabTitle {{ font-size: 18px; font-weight: 600; }}
QLabel[role="desc"], QLabel[role="sub"] {{ color: {t['muted']}; font-size: 12px; }}
QLabel[role="sub"] {{ font-size: 11px; }}
QLabel[role="section"] {{ color: {t['muted']}; font-size: 11px; font-weight: 600; letter-spacing: 1px; }}
QLabel[role="value"] {{ font-family: "{f['mono']}"; font-size: 13px; }}
QLabel[role="note"] {{ color: {t['muted']}; font-size: 11px; }}

QSlider {{ min-height: 18px; max-height: 18px; }}
QSlider::groove:horizontal {{ height: 4px; background: {t['track']}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 2px; }}
QSlider[channel="red_scale"]::sub-page:horizontal {{ background: {CHANNEL_COLORS['red_scale']}; }}
QSlider[channel="green_scale"]::sub-page:horizontal {{ background: {CHANNEL_COLORS['green_scale']}; }}
QSlider[channel="blue_scale"]::sub-page:horizontal {{ background: {CHANNEL_COLORS['blue_scale']}; }}
QSlider::sub-page:horizontal:disabled {{ background: {t['border2']}; }}
QSlider::add-page:horizontal {{ background: {t['track']}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: #ffffff; border: 1px solid {t['border2']}; width: 14px; height: 14px;
    margin: -6px 0; border-radius: 8px; }}
QSlider::handle:horizontal:disabled {{ background: {t['disabled']}; }}

/* keycaps, inputs */
QPushButton[kind="keycap"] {{ font-family: "{f['mono']}"; font-size: 12px; background: {t['input']};
    border: 1px solid {t['border2']}; border-bottom-width: 2px; min-width: 140px; min-height: 30px; padding: 0 10px; }}
QPushButton[kind="keycap"]:hover {{ border-color: {t['faint']}; }}
QPushButton[kind="keycap"][empty="true"] {{ color: {t['faint']}; }}
QPushButton[kind="keycap"][state="recording"] {{ border-color: {ACCENT}; color: {t['accent_text']}; }}
QPushButton[kind="keycap"][state="bad"] {{ border-color: {DANGER_TEXT}; color: {DANGER_TEXT}; }}
QLineEdit {{ background: {t['input']}; border: 1px solid {t['border']}; border-radius: 6px; padding: 0 10px;
    min-height: 32px; selection-background-color: {ACCENT}; selection-color: {ON_ACCENT}; }}
QLineEdit:focus {{ border-color: {t['border2']}; }}
QLineEdit:disabled {{ color: {t['muted']}; }}
QLineEdit[conflict="true"] {{ border-color: {DANGER_TEXT}; }}
QLabel#dirtyText {{ color: {t['accent_text']}; font-size: 12px; }}
QLabel#nameError {{ background: {DANGER}; color: #ffffff; font-size: 12px; font-weight: 600; border-radius: 6px; padding: 5px 10px; }}

/* presets */
#presetRow {{ border: 1px solid transparent; border-radius: 6px; background: transparent; }}
#presetRow:hover {{ background: {t['hover']}; }}
#presetRow[selected="true"] {{ background: {t['hover']}; border-color: {ACCENT}; }}
#presetRow QLabel {{ background: transparent; }}
#presetRow[selected="true"] QLabel#presetName {{ font-weight: 600; }}
QLabel[mono="true"][role="hk"] {{ color: {t['faint']}; }}

/* monitors */
#monCard {{ border: 1px solid {t['border']}; border-radius: 8px; background: transparent; }}
#monCard:hover {{ border-color: {t['faint']}; }}
#monCard[selected="true"] {{ border-color: {ACCENT}; background: {t['surface']}; }}
#monCard QLabel {{ background: transparent; }}
QLabel#primaryTag {{ background: {t['text2']}; color: {t['bg']}; font-size: 9px; font-weight: 700; border-radius: 4px; padding: 1px 6px; }}

/* hotkey rows */
#hkRow {{ border-bottom: 1px solid {t['border']}; }}

/* dialogs */
#dialogCard {{ background: {t['surface']}; border: 1px solid {t['border2']}; border-radius: 10px; }}
#dialogCard QLabel {{ background: transparent; }}
#dialogTitle {{ font-size: 16px; font-weight: 600; }}
#settingRow {{ border-bottom: 1px solid {t['border']}; }}

/* scrollbars */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px 2px 2px 0; }}
QScrollBar::handle:vertical {{ background: {t['border']}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {t['border2']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}

/* tray menu */
QMenu {{ background: {t['surface']}; border: 1px solid {t['border2']}; padding: 4px; }}
QMenu::item {{ padding: 6px 24px 6px 12px; border-radius: 4px; }}
QMenu::item:selected {{ background: {t['hover']}; }}
"""
