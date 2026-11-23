"""
NightVision main window (PySide6 / Qt).

Layout: title bar | left sidebar (sections) | content + action bar | right sidebar (presets)
The window is borderless but Windows still handles moving, resizing and Snap (see frameless.py).
Sidebars adapt to the window width instead of being draggable:
  - left sidebar collapses to icons below 900 px
  - presets sidebar is 24% of the width, clamped to 220-320 px
  - the preview sits beside the sliders when there is room, under them otherwise
"""
import math

from PySide6.QtCore import Qt, QObject, Signal, QTimer, QSize, QVariantAnimation, QEvent, QByteArray, QPoint
from PySide6.QtGui import QPixmap, QImage, QGuiApplication, QIcon
from PySide6.QtWidgets import (QApplication, QWidget, QLabel, QPushButton, QHBoxLayout, QVBoxLayout, QBoxLayout,
                               QStackedWidget, QScrollArea, QLineEdit, QFrame, QSizePolicy)
from PIL import Image, ImageDraw, ImageEnhance

from . import theme
from .theme import T, G, ACCENT, OK_GREEN, CHANNEL_COLORS
from .frameless import FramelessWindow
from .widgets import (set_prop, dot_icon, glyph_icon, glyph_label, separator, Dot, ToggleSwitch, CheckBox,
                      ValueSlider, ClickLabel, NavButton, PresetRow, PreviewWidget, Overlay)
from .utils import resource_path, enumerate_monitors, APP_NAME
from .input_manager import MODIFIER_VKS, format_hotkey, parse_hotkey
from .config import VALUE_KEYS, DEFAULT_VALUES, DEFAULT_PRESET, NEW_PRESET_BASE
from .gamma import compute_curves
from . import vibrance as vib

F2 = "{:.2f}"
TABS = [
    {"id": "lum", "label": "Luminance", "icon": "sun",
     "desc": "Brightness, contrast and gamma applied to the monitor gamma ramp.",
     "sliders": [("brightness", "Brightness", 0.0, 1.0, 0.01, F2), ("contrast", "Contrast", 0.0, 1.0, 0.01, F2),
                 ("gamma", "Gamma", 0.1, 5.0, 0.1, F2)]},
    {"id": "rgb", "label": "Color channels", "icon": "palette",
     "desc": "Per-channel multiplier. 1.00 = unchanged.",
     "sliders": [("red_scale", "Red", 0.0, 2.0, 0.05, F2), ("green_scale", "Green", 0.0, 2.0, 0.05, F2),
                 ("blue_scale", "Blue", 0.0, 2.0, 0.05, F2)]},
    {"id": "vib", "label": "Vibrance", "icon": "drop", "title": "Digital Vibrance",
     "desc": "Hardware saturation from the NVIDIA driver. 50% is the driver default, 0% is grayscale.",
     "sliders": [("vibrance", "Vibrance", vib.MIN_PERCENT, vib.MAX_PERCENT, 1, "{:.0f}%")]},
    {"id": "hk", "label": "Hotkeys", "icon": "keyboard", "gap": True,
     "desc": "Global shortcuts. They work while a game is focused."},
    {"id": "mon", "label": "Monitors", "icon": "monitor",
     "desc": "Choose which screens the filter is applied to."},
]
SLIDER_TABS = [t["id"] for t in TABS if t.get("sliders")]

MIN_W, MIN_H = 760, 480
DEFAULT_W, DEFAULT_H = 1000, 620
LIST_MAX_W = 640


def pretty_hotkey(hk):
    """'ctrl+shift+f10' -> 'Ctrl+Shift+F10'"""
    if not hk:
        return ""
    return "+".join(p.upper() if len(p) == 1 or (p[:1] == "f" and p[1:].isdigit()) else p.title()
                    for p in hk.split("+"))


def vibrance_factor(percent):
    """Approximate the driver's vibrance as a PIL saturation factor (preview only)."""
    p = float(percent)
    return p / 50.0 if p <= 50 else 1.0 + (p - 50) / 50.0 * 1.5


def _scene():
    """Night scene + grey ramp, drawn once at 960x540."""
    W, H = 960, 540
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    horizon = int(H * 0.5)
    for y in range(H):
        if y < horizon:
            t = y / horizon
            c = tuple(int(a + (b - a) * t) for a, b in zip((11, 16, 32), (26, 34, 56)))
        else:
            t = (y - horizon) / (H - horizon)
            c = tuple(int(a + (b - a) * t) for a, b in zip((29, 36, 24), (14, 18, 11)))
        d.line([(0, y), (W, y)], fill=c)
    d.ellipse([W * 0.86, H * 0.1, W * 0.86 + 44, H * 0.1 + 44], fill=(216, 210, 181))
    d.rectangle([W * 0.06, H * 0.40, W * 0.23, H * 0.64], fill=(76, 60, 44))
    d.polygon([(W * 0.045, H * 0.40), (W * 0.145, H * 0.30), (W * 0.245, H * 0.40)], fill=(58, 44, 34))
    d.rectangle([W * 0.10, H * 0.46, W * 0.13, H * 0.52], fill=(185, 148, 80))
    d.rectangle([W * 0.17, H * 0.46, W * 0.20, H * 0.52], fill=(42, 33, 24))
    d.rectangle([W * 0.31, H * 0.34, W * 0.34, H * 0.64], fill=(47, 74, 37))
    d.ellipse([W * 0.28, H * 0.22, W * 0.37, H * 0.40], fill=(36, 57, 28))
    d.rectangle([W * 0.53, H * 0.65, W * 0.546, H * 0.76], fill=(111, 125, 136))
    d.rounded_rectangle([W * 0.64, H * 0.72, W * 0.82, H * 0.80], radius=6, fill=(106, 40, 34))
    for x in range(W):  # grey ramp: shows what gamma does to the dark end
        v = int(255 * x / (W - 1))
        d.line([(x, int(H * 0.9)), (x, H)], fill=(v, v, v))
    return img


class Bridge(QObject):
    """Signals used to reach the GUI thread from the hotkey/IPC/tray threads."""
    toggle = Signal()
    load_preset = Signal(str)
    hotkey_status = Signal(list)
    show = Signal()


def label(text, role=None, obj=None):
    lbl = QLabel(text)
    if role:
        lbl.setProperty("role", role)
    if obj:
        lbl.setObjectName(obj)
    return lbl


def button(text, kind, cursor=True):
    b = QPushButton(text)
    b.setProperty("kind", kind)
    if cursor:
        b.setCursor(Qt.PointingHandCursor)
    return b


class SettingsApp(FramelessWindow):
    def __init__(self, config_manager, gamma_controller, vibrance_controller, input_manager_ref, on_quit=None):
        super().__init__()
        self.config = config_manager
        self.gamma = gamma_controller
        self.vibrance = vibrance_controller
        # Set later by main (InputManager needs callbacks into this window)
        self.input_manager = input_manager_ref
        self.on_quit = on_quit

        self.bridge = Bridge()
        self.bridge.toggle.connect(self.toggle_filter)
        self.bridge.load_preset.connect(self.load_preset)
        self.bridge.hotkey_status.connect(self.show_hotkey_status)
        self.bridge.show.connect(self.show_window)

        self.filter_on = False
        self._rec = None
        self._failed_hotkeys = set()
        self.hk_buttons = {}
        self.monitors = enumerate_monitors()
        self._vib_ok = {m["device"]: self.vibrance.supports(m["device"]) for m in self.monitors}
        self.active = self.config.current_settings.get("active_preset", DEFAULT_PRESET)
        if self.active not in self.config.presets:
            self.active = DEFAULT_PRESET
        self.draft = self.config.preset_values(self.active)
        self.tab = "lum"
        self._layout_state = {}
        self._scene = _scene()
        self._name_tip = None

        self._preview_timer = QTimer(self, singleShot=True, interval=16, timeout=self._render_preview)
        self._apply_timer = QTimer(self, singleShot=True, interval=15, timeout=self.apply_filter)
        self._tip_timer = QTimer(self, singleShot=True, interval=2200, timeout=self._close_name_error)

        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(QIcon(resource_path("icon.ico")))
        self.setMinimumSize(MIN_W, MIN_H)
        self.setObjectName("root")
        self.setAttribute(Qt.WA_StyledBackground)

        theme.set_theme(self.config.current_settings.get("dark_mode", True))
        QApplication.instance().setStyleSheet(theme.stylesheet())
        self.set_border_color(T["border2"])
        self.set_topmost(self.config.current_settings.get("always_on_top", False))

        self._build_ui()
        self._restore_geometry()
        self.show_tab("lum")
        self.refresh_presets()
        self._set_draft(self.draft, self.active)
        self.update_status_visuals()

    # ------------------------------------------------------------------ window

    def _restore_geometry(self):
        geo = self.config.current_settings.get("window_geometry")
        if geo:
            try:
                if self.restoreGeometry(QByteArray.fromHex(geo.encode())):
                    return
            except Exception:
                pass
        area = QGuiApplication.primaryScreen().availableGeometry()
        w, h = min(DEFAULT_W, area.width()), min(DEFAULT_H, area.height())
        self.setGeometry(area.x() + (area.width() - w) // 2, area.y() + (area.height() - h) // 2, w, h)

    def _save_geometry(self):
        if self.isVisible():
            self.config.update_setting("window_geometry", bytes(self.saveGeometry().toHex()).decode())

    def show_window(self):
        if self.isMinimized():
            self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()

    def hide_window(self):
        self._save_geometry()
        self._close_name_error()
        self.hide()

    def closeEvent(self, e):
        if self.config.current_settings.get("close_to_tray", True) or not self.on_quit:
            e.ignore()
            self.hide_window()
        else:
            self._save_geometry()
            e.accept()
            self.on_quit()

    def changeEvent(self, e):
        if e.type() == QEvent.WindowStateChange and getattr(self, "max_button", None) is not None:
            self.max_button.setText(G["restore"] if self.isMaximized() else G["max"])
            self.max_button.setToolTip("Restore" if self.isMaximized() else "Maximize")
        super().changeEvent(e)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._apply_layout()
        if self._name_tip is not None:
            self._close_name_error()

    # ------------------------------------------------------------------ building

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_title_bar())
        root.addWidget(separator())

        body = QWidget(objectName="body")
        body.setAttribute(Qt.WA_StyledBackground)
        bl = QHBoxLayout(body)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(0)
        bl.addWidget(self._build_nav())
        bl.addWidget(separator(vertical=True))
        bl.addWidget(self._build_main(), 1)
        bl.addWidget(separator(vertical=True))
        bl.addWidget(self._build_presets_panel())
        root.addWidget(body, 1)
        self._refresh_icons()

    def _build_title_bar(self):
        bar = QWidget(objectName="titleBar")
        bar.setAttribute(Qt.WA_StyledBackground)
        bar.setFixedHeight(44)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(14, 0, 0, 0)
        lay.setSpacing(0)

        icon = QLabel()
        icon.setPixmap(QIcon(resource_path("icon.ico")).pixmap(QSize(22, 22)))
        lay.addWidget(icon)
        lay.addSpacing(10)
        lay.addWidget(label(APP_NAME, obj="appTitle"))
        lay.addSpacing(12)
        self.status_badge = QPushButton(objectName="statusPill")
        self.status_badge.setCursor(Qt.PointingHandCursor)
        self.status_badge.setIconSize(QSize(8, 8))
        self.status_badge.clicked.connect(self.toggle_filter)
        lay.addWidget(self.status_badge)
        lay.addSpacing(10)
        self.title_hk = QLabel()
        self.title_hk.setProperty("mono", True)
        lay.addWidget(self.title_hk)
        lay.addStretch(1)

        gear = button(G["gear"], "glyph")
        gear.setFixedSize(40, 32)
        gear.setStyleSheet("font-size: 15px;")
        gear.setToolTip("Settings")
        gear.clicked.connect(self.open_settings)
        lay.addWidget(gear)
        lay.addSpacing(6)
        for glyph, tip, slot, name in ((G["min"], "Minimize", self.showMinimized, "minBtn"),
                                       (G["max"], "Maximize", self.toggle_maximize, "maxBtn"),
                                       (G["close"], "Close", self.close, "closeBtn")):
            b = button(glyph, "caption", cursor=False)
            b.setObjectName(name)
            b.setToolTip(tip)
            b.clicked.connect(slot)
            lay.addWidget(b)
            if name == "maxBtn":
                self.max_button = b
        self.title_bar = bar
        return bar

    def _build_nav(self):
        nav = QWidget()
        nav.setFixedWidth(188)
        lay = QVBoxLayout(nav)
        lay.setContentsMargins(8, 10, 8, 12)
        lay.setSpacing(2)
        self.nav = nav
        self.nav_buttons = {}
        for t in TABS:
            if t.get("gap"):
                lay.addSpacing(8)
                lay.addWidget(separator())
                lay.addSpacing(8)
            b = NavButton(G[t["icon"]], t["label"])
            b.set_compact(False)
            b.clicked.connect(lambda _=False, tid=t["id"]: self.show_tab(tid))
            lay.addWidget(b)
            self.nav_buttons[t["id"]] = b
        lay.addStretch(1)

        self.nav_footer_labels = []

        def line(dot, text, indent=False):
            row = QHBoxLayout()
            row.setSpacing(7)
            row.setContentsMargins(12, 0, 0, 0)
            if dot is not None:
                row.addWidget(dot, 0, Qt.AlignVCenter)
            elif indent:
                row.addSpacing(14)
            lbl = label(text, role="footer")
            row.addWidget(lbl, 1)
            self.nav_footer_labels.append(lbl)
            lay.addLayout(row)
            self.nav_footer_rows.append(row)
            return lbl

        self.nav_footer_rows = []
        nv = self.vibrance.available
        d1 = Dot(OK_GREEN if nv else (lambda: T["off_dot"]))
        d1.setToolTip("NVIDIA driver found · Digital Vibrance available" if nv
                      else "No NVIDIA driver · Digital Vibrance unavailable")
        line(d1, "NVIDIA driver found" if nv else "No NVIDIA driver")
        line(None, "Digital Vibrance available" if nv else "Vibrance unavailable", indent=True)
        lay.addSpacing(6)
        self.mon_dot = Dot(lambda: ACCENT if self.filter_on else T["off_dot"])
        self.mon_summary = line(self.mon_dot, "")
        return nav

    def _build_main(self):
        main = QWidget()
        lay = QVBoxLayout(main)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        head = QVBoxLayout()
        head.setContentsMargins(24, 18, 24, 4)
        head.setSpacing(4)
        self.tab_title = label("", obj="tabTitle")
        self.tab_desc = label("", role="desc")
        self.tab_desc.setWordWrap(True)
        head.addWidget(self.tab_title)
        head.addWidget(self.tab_desc)
        lay.addLayout(head)

        self.pages = QStackedWidget()
        self.editor_page = self._build_editor_page()
        self.pages.addWidget(self.editor_page)
        self.list_page = QScrollArea()
        self.list_page.setWidgetResizable(True)
        self.list_page.setFrameShape(QFrame.NoFrame)
        self.list_page.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.pages.addWidget(self.list_page)
        wrap = QVBoxLayout()
        wrap.setContentsMargins(24, 12, 24, 16)
        wrap.addWidget(self.pages)
        lay.addLayout(wrap, 1)

        lay.addWidget(separator())
        lay.addWidget(self._build_action_bar())
        return main

    def _build_editor_page(self):
        page = QWidget()
        self.editor_layout = QBoxLayout(QBoxLayout.TopToBottom, page)
        self.editor_layout.setContentsMargins(0, 0, 0, 0)
        self.editor_layout.setSpacing(24)

        self.slider_stack = QStackedWidget()
        self.sliders = {}
        for t in TABS:
            if not t.get("sliders"):
                continue
            col = QWidget()
            cl = QVBoxLayout(col)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setSpacing(18)
            for key, text, lo, hi, step, fmt in t["sliders"]:
                cl.addLayout(self._create_slider(key, text, lo, hi, step, fmt))
            if t["id"] == "vib":
                self.vib_note = label("", role="note")
                self.vib_note.setWordWrap(True)
                cl.addWidget(self.vib_note)
                if not self.vibrance.available:
                    self.sliders["vibrance"]["slider"].setEnabled(False)
            cl.addStretch(1)
            self.slider_stack.addWidget(col)
        self.editor_layout.addWidget(self.slider_stack)

        self.preview_box = QWidget()
        prev = QVBoxLayout(self.preview_box)
        prev.setContentsMargins(0, 0, 0, 0)
        prev.setSpacing(8)
        prev.addWidget(label("PREVIEW", role="section"))
        self.preview = PreviewWidget()
        self.preview.resized.connect(self._on_preview_resized)
        prev.addWidget(self.preview, 1)
        prev.addStretch(0)
        self.editor_layout.addWidget(self.preview_box, 1)
        return page

    def _create_slider(self, key, text, lo, hi, step, fmt):
        box = QVBoxLayout()
        box.setSpacing(8)
        head = QHBoxLayout()
        head.addWidget(QLabel(text))
        head.addStretch(1)
        value = ClickLabel("")
        value.setProperty("role", "value")
        value.setToolTip("Double-click to reset")
        value.setCursor(Qt.PointingHandCursor)
        head.addWidget(value)
        box.addLayout(head)
        slider = ValueSlider(lo, hi, step, DEFAULT_VALUES[key], channel=key if key in CHANNEL_COLORS else None)
        box.addWidget(slider)

        def on_change(v):
            value.setText(fmt.format(v))
            self.draft[key] = v
            self._on_draft_changed()

        def reset():
            slider.set_float(DEFAULT_VALUES[key])
            on_change(DEFAULT_VALUES[key])

        slider.valueChangedF.connect(on_change)
        slider.reset.connect(reset)
        value.doubleClicked.connect(reset)
        self.sliders[key] = {"slider": slider, "label": value, "fmt": fmt}
        return box

    def _build_action_bar(self):
        bar = QWidget()
        bar.setFixedHeight(56)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(24, 0, 16, 0)
        lay.setSpacing(4)
        self.ab_label = label("PRESET NAME", role="section")
        lay.addWidget(self.ab_label)

        self.name_wrap = QWidget()
        self.name_wrap.setMinimumWidth(90)
        self.name_wrap.setMaximumWidth(332)
        self.name_wrap.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        nl = QHBoxLayout(self.name_wrap)
        nl.setContentsMargins(6, 0, 6, 0)  # room for the 'name in use' shake
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Preset name")
        self.name_edit.textEdited.connect(self._on_name_typed)
        self.name_edit.returnPressed.connect(self.save_preset)
        nl.addWidget(self.name_edit)
        lay.addWidget(self.name_wrap, 1)

        self.btn_dup = button("Duplicate", "ghost")
        self.btn_dup.setIconSize(QSize(14, 14))
        self.btn_dup.setToolTip("Duplicate this preset")
        self.btn_dup.clicked.connect(self.duplicate_preset)
        lay.addWidget(self.btn_dup)

        self.dirty_box = QWidget()
        dl = QHBoxLayout(self.dirty_box)
        dl.setContentsMargins(4, 0, 0, 0)
        dl.setSpacing(6)
        dl.addWidget(Dot(ACCENT), 0, Qt.AlignVCenter)
        self.dirty_text = label("Unsaved changes", obj="dirtyText")
        dl.addWidget(self.dirty_text)
        self.dirty_box.setToolTip("Unsaved changes")
        lay.addWidget(self.dirty_box)
        lay.addStretch(1)

        self.btn_discard = button("Discard", "outline")
        self.btn_discard.clicked.connect(self.discard_changes)
        lay.addWidget(self.btn_discard)
        self.btn_save = button("Save", "primary")
        self.btn_save.clicked.connect(self.save_preset)
        lay.addWidget(self.btn_save)
        return bar

    def _build_presets_panel(self):
        aside = QWidget()
        aside.setFixedWidth(240)
        self.aside = aside
        lay = QVBoxLayout(aside)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        head = QHBoxLayout()
        head.setContentsMargins(16, 14, 12, 10)
        self.presets_title = label("PRESETS", role="section")
        head.addWidget(self.presets_title)
        head.addStretch(1)
        self.btn_new = button("New", "new")
        self.btn_new.setIconSize(QSize(12, 12))
        self.btn_new.clicked.connect(self.new_preset)
        head.addWidget(self.btn_new)
        lay.addLayout(head)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        holder = QWidget()
        self.preset_layout = QVBoxLayout(holder)
        self.preset_layout.setContentsMargins(8, 0, 8, 12)
        self.preset_layout.setSpacing(2)
        scroll.setWidget(holder)
        lay.addWidget(scroll, 1)
        return aside

    def _refresh_icons(self):
        """Icons drawn from glyphs carry their colour: redraw them for the current theme."""
        self.btn_new.setIcon(glyph_icon(G["add"], theme.ON_ACCENT, 12, 14))
        self.btn_dup.setIcon(glyph_icon(G["copy"], T["text2"], 14))
        for b in self.nav_buttons.values():
            b.refresh_icon()

    # ------------------------------------------------------------------ responsive layout

    def _apply_layout(self):
        W = self.width()
        st = self._layout_state

        compact_nav = W < 900
        if st.get("compact_nav") != compact_nav:
            st["compact_nav"] = compact_nav
            self.nav.setFixedWidth(60 if compact_nav else 188)
            for b in self.nav_buttons.values():
                b.set_compact(compact_nav)
            for lbl in self.nav_footer_labels:
                lbl.setVisible(not compact_nav)
            for row in self.nav_footer_rows:
                row.setContentsMargins(18 if compact_nav else 12, 0, 0, 0)
            self.mon_dot.setToolTip(self.mon_summary.text() if compact_nav else "")

        aside_w = int(max(220, min(320, W * 0.24)))
        if st.get("aside_w") != aside_w:
            st["aside_w"] = aside_w
            self.aside.setFixedWidth(aside_w)

        main_w = W - (60 if compact_nav else 188) - aside_w - 2
        compact_bar = main_w < 640
        if st.get("compact_bar") != compact_bar:
            st["compact_bar"] = compact_bar
            self.ab_label.setVisible(not compact_bar)
            self.dirty_text.setVisible(not compact_bar)
            self.btn_dup.setText("" if compact_bar else "Duplicate")

        content_w = main_w - 48
        side = content_w >= 600
        if st.get("side") != side:
            st["side"] = side
            self.editor_layout.setDirection(QBoxLayout.LeftToRight if side else QBoxLayout.TopToBottom)
            if not side:
                self.slider_stack.setMinimumWidth(0)
                self.slider_stack.setMaximumWidth(16777215)
        if side:
            self.slider_stack.setFixedWidth(int(min(400, max(260, content_w * 0.42))))
        self.slider_stack.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred if side else QSizePolicy.Maximum)

    # ------------------------------------------------------------------ tabs

    def show_tab(self, tab_id):
        self.tab = tab_id
        tab = next(t for t in TABS if t["id"] == tab_id)
        for tid, b in self.nav_buttons.items():
            b.setChecked(tid == tab_id)
        self.tab_title.setText(tab.get("title", tab["label"]))
        self.tab_desc.setText(tab["desc"])
        if tab_id in SLIDER_TABS:
            self.slider_stack.setCurrentIndex(SLIDER_TABS.index(tab_id))
            self.pages.setCurrentWidget(self.editor_page)
            if tab_id == "vib":
                self._update_vib_note()
            self._schedule_preview()
        else:
            self._build_list_page(tab_id)
            self.pages.setCurrentWidget(self.list_page)

    def _update_vib_note(self):
        note = ""
        if not self.vibrance.available:
            note = "NVIDIA driver not found: Digital Vibrance is unavailable."
        elif not any(self._vib_ok.get(d) for d in self._selected_devices()):
            note = "None of the selected monitors is connected to the NVIDIA card."
        elif not self.vibrance.full_range:
            note = "This driver only supports 50-100%."
        self.vib_note.setText(note)
        self.vib_note.setVisible(bool(note))

    def _build_list_page(self, tab_id):
        """Hotkeys / Monitors: a left-aligned column, max 640 px (rows read badly stretched wide)."""
        holder = QWidget()
        outer = QHBoxLayout(holder)
        outer.setContentsMargins(0, 0, 12, 0)
        column = QWidget()
        column.setMaximumWidth(LIST_MAX_W)
        lay = QVBoxLayout(column)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        if tab_id == "hk":
            self._fill_hotkeys(lay)
        else:
            self._fill_monitors(lay)
        lay.addStretch(1)
        outer.addWidget(column, 1)
        outer.addStretch(0)
        self.list_page.setWidget(holder)

    def _fill_hotkeys(self, lay):
        self.hk_buttons = {}

        def header(text, first=False):
            if not first:
                lay.addSpacing(14)
            lay.addWidget(label(text, role="section"))
            lay.addSpacing(2)

        def row(key, title, sub, hotkey):
            r = QFrame(objectName="hkRow")
            rl = QHBoxLayout(r)
            rl.setContentsMargins(0, 10, 0, 10)
            rl.setSpacing(6)
            texts = QVBoxLayout()
            texts.setSpacing(1)
            texts.addWidget(QLabel(title))
            texts.addWidget(label(sub, role="sub"))
            rl.addLayout(texts, 1)
            cap = button("", "keycap")
            cap.clicked.connect(lambda: self._record_hotkey_for(key))
            rl.addWidget(cap)
            clear = button("", "glyph")
            clear.setFixedSize(28, 28)
            clear.setIcon(glyph_icon(G["x"], T["muted"], 10, 12))  # drawn icon: no ClearType colour fringes
            clear.setToolTip("Remove hotkey")
            clear.clicked.connect(lambda: self._set_hotkey(key, None))
            rl.addWidget(clear)
            lay.addWidget(r)
            self.hk_buttons[key] = [cap, hotkey]

        header("GENERAL", first=True)
        row(None, "Toggle filter", "Turn the filter on or off", self.config.current_settings.get("hotkey"))
        header("PRESETS")
        for name in self.config.get_preset_names():
            row(name, name, "Load this preset", self.config.presets[name].get("hotkey"))
        lay.addSpacing(12)
        lay.addWidget(label("Click a key, then press the new combination. Esc cancels.", role="note"))
        self.show_hotkey_status()

    def _fill_monitors(self, lay):
        selected = set(self._selected_devices())
        for m in self.monitors:
            on = m["device"] in selected
            card = QFrame(objectName="monCard")
            card.setAttribute(Qt.WA_Hover)
            card.setCursor(Qt.PointingHandCursor)
            card.setProperty("selected", on)
            cl = QHBoxLayout(card)
            cl.setContentsMargins(16, 14, 16, 14)
            cl.setSpacing(14)
            box = CheckBox(on)
            box.toggled.connect(lambda checked, d=m["device"]: self._toggle_monitor(d, checked))
            cl.addWidget(box)
            cl.addWidget(glyph_label(G["monitor"], 22, T["muted"]))
            texts = QVBoxLayout()
            texts.setSpacing(2)
            name_row = QHBoxLayout()
            name_row.setSpacing(8)
            name_row.addWidget(QLabel(m["name"]))
            if m["primary"]:
                name_row.addWidget(label("PRIMARY", obj="primaryTag"))
            name_row.addStretch(1)
            texts.addLayout(name_row)
            device = m["device"].replace("\\\\.\\", "")
            spec = f"{device} · {m['width']} × {m['height']} · {m['refresh']} Hz"
            ok = self._vib_ok.get(m["device"])
            if not ok:
                spec += f" · {m['gpu']}"
            texts.addWidget(label(spec, role="sub"))
            cl.addLayout(texts, 1)
            cl.addWidget(label("Gamma + Vibrance" if ok else "Gamma only", role="sub"))
            card.mousePressEvent = lambda e, b=box: b.toggle()
            lay.addWidget(card)
            lay.addSpacing(10)
        note = label("Gamma and color changes work on every monitor. Digital Vibrance only on monitors "
                     "connected to the NVIDIA card.", role="note")
        note.setWordWrap(True)
        lay.addWidget(note)

    # ------------------------------------------------------------------ monitors

    def _selected_devices(self):
        present = [m["device"] for m in self.monitors]
        chosen = [d for d in self.config.current_settings.get("monitors") or [] if d in present]
        if not chosen:
            primary = next((m["device"] for m in self.monitors if m["primary"]), present[0] if present else None)
            chosen = [primary] if primary else []
        return chosen

    def _toggle_monitor(self, device, checked):
        chosen = set(self._selected_devices())
        if checked:
            chosen.add(device)
        else:
            chosen.discard(device)
        if chosen:  # at least one monitor stays selected
            self.config.update_setting("monitors", [m["device"] for m in self.monitors if m["device"] in chosen])
            if self.filter_on:
                self.apply_filter()
        QTimer.singleShot(0, lambda: self._build_list_page("mon"))  # not while the checkbox is emitting
        self.update_status_visuals()

    def _monitor_summary(self):
        n, total = len(self._selected_devices()), len(self.monitors)
        if self.filter_on:
            return f"Active on {n} of {total} monitor{'s' if total != 1 else ''}"
        return f"Filter off · {n} of {total} selected"

    # ------------------------------------------------------------------ preview

    def _on_preview_resized(self):
        # keep a pleasant aspect: never taller than ~16:10 of its width
        self.preview.setMaximumHeight(max(100, int(self.preview.width() * 0.62)))
        self._schedule_preview()

    def _schedule_preview(self):
        self._preview_timer.start()

    def _render_preview(self):
        if not self.preview.isVisible():
            return
        dpr = self.devicePixelRatioF() or 1.0
        w, h = max(1, int(self.preview.width() * dpr)), max(1, int(self.preview.height() * dpr))
        # 'cover' crop of the 16:9 scene to the widget's aspect, rendered at device resolution
        sw, sh = self._scene.size
        scale = max(w / sw, h / sh)
        cw, ch = w / scale, h / scale
        box = ((sw - cw) / 2, (sh - ch) / 2, (sw + cw) / 2, (sh + ch) / 2)
        img = self._scene.resize((w, h), Image.BILINEAR, box=box)
        if self.filter_on:
            curves = compute_curves(self.draft)
            img = img.point([int(v * 255 + 0.5) for curve in curves for v in curve])
            factor = vibrance_factor(self.draft["vibrance"])
            if abs(factor - 1.0) > 0.01:
                img = ImageEnhance.Color(img).enhance(factor)
        qimg = QImage(img.tobytes(), w, h, 3 * w, QImage.Format_RGB888).copy()
        qimg.setDevicePixelRatio(dpr)
        self.preview.set_image(qimg)

    # ------------------------------------------------------------------ presets panel

    def refresh_presets(self):
        while self.preset_layout.count():
            item = self.preset_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        names = self.config.get_preset_names()
        self.presets_title.setText(f"PRESETS · {len(names)}")
        self.preset_rows = {}
        for i, name in enumerate(names):
            if i == 1:
                self.preset_layout.addSpacing(6)
                self.preset_layout.addWidget(separator())
                self.preset_layout.addSpacing(6)
            row = PresetRow(name, pretty_hotkey(self.config.presets[name].get("hotkey")), name == DEFAULT_PRESET)
            row.set_selected(name == self.active)
            row.clicked.connect(self.select_preset)
            row.deleteRequested.connect(self.confirm_delete)
            self.preset_layout.addWidget(row)
            self.preset_rows[name] = row
        self.preset_layout.addStretch(1)
        self._refresh_dirty_marks()

    def _is_dirty(self):
        saved = self.config.preset_values(self.active)
        if any(abs(float(self.draft[k]) - float(saved[k])) > 1e-6 for k in VALUE_KEYS):
            return True
        return self.active != DEFAULT_PRESET and self.name_edit.text().strip() != self.active

    def _refresh_dirty_marks(self):
        dirty = self._is_dirty()
        for name, row in self.preset_rows.items():
            row.set_dirty(dirty and name == self.active)
        return dirty

    def _refresh_action_bar(self):
        dirty = self._refresh_dirty_marks()
        is_default = self.active == DEFAULT_PRESET
        self.name_edit.setEnabled(not is_default)
        self.name_edit.setToolTip("The Default preset can't be renamed or deleted" if is_default else "")
        text = self.name_edit.text().strip()
        conflict = not is_default and text != self.active and self.config.name_taken(text, exclude=self.active)
        set_prop(self.name_edit, "conflict", conflict)
        self.btn_dup.setVisible(not is_default)
        self.dirty_box.setVisible(dirty)
        self.btn_discard.setEnabled(dirty)
        self.btn_save.setEnabled(dirty)

    def _on_name_typed(self, _text):
        self._close_name_error()
        self._refresh_action_bar()

    def _on_draft_changed(self):
        self._refresh_action_bar()
        self._schedule_preview()
        if self.filter_on:
            self._apply_timer.start()

    def _set_draft(self, values, name):
        self.draft = dict(values)
        self.name_edit.setText(name)
        for key, w in self.sliders.items():
            w["slider"].set_float(self.draft[key])
            w["label"].setText(w["fmt"].format(self.draft[key]))
        self._on_draft_changed()

    # --- preset actions

    def select_preset(self, name):
        if name not in self.config.presets:
            return
        self.active = name
        self.config.update_setting("active_preset", name)
        for n, row in self.preset_rows.items():
            row.set_selected(n == name)
        self._set_draft(self.config.preset_values(name), name)

    def load_preset(self, name):
        """Hotkey / tray: switch preset (applied at once if the filter is on)."""
        self.select_preset(name)

    def _after_presets_changed(self):
        self.refresh_presets()
        if self.tab == "hk":
            self._build_list_page("hk")
        if self.input_manager:
            self.input_manager.register_shortcuts()

    def new_preset(self):
        name = self.config.create_preset(self.config.free_name(NEW_PRESET_BASE, numbered=True), DEFAULT_VALUES)
        if self.tab not in SLIDER_TABS:
            self.show_tab("lum")
        self._after_presets_changed()
        self.select_preset(name)
        self.name_edit.setFocus()
        self.name_edit.selectAll()

    def duplicate_preset(self):
        if self.active == DEFAULT_PRESET:
            return
        name = self.config.create_preset(self.config.free_name(f"{self.active} (copy)", numbered=False), self.draft)
        self._after_presets_changed()
        self.select_preset(name)

    def save_preset(self):
        if not self._is_dirty():
            return
        new_name = self.name_edit.text().strip()
        if (self.active != DEFAULT_PRESET and new_name and new_name != self.active
                and self.config.name_taken(new_name, exclude=self.active)):
            self._show_name_error()
            return
        final = self.config.update_preset(self.active, self.draft,
                                          new_name=None if self.active == DEFAULT_PRESET else new_name)
        if final is None:
            self._show_name_error()
            return
        renamed = final != self.active
        self.active = final
        self.config.update_setting("active_preset", final)
        self.name_edit.setText(final)
        if renamed:
            self._after_presets_changed()
        self._refresh_action_bar()

    def discard_changes(self):
        self._set_draft(self.config.preset_values(self.active), self.active)

    def confirm_delete(self, name):
        hk = self.config.presets.get(name, {}).get("hotkey")
        text = "This can't be undone." + (f" Its hotkey {pretty_hotkey(hk)} will be freed." if hk else "")

        def do_delete():
            was_active = name == self.active
            if self.config.delete_preset(name):
                self._after_presets_changed()
                if was_active:
                    self.select_preset(DEFAULT_PRESET)

        self._confirm(f"Delete “{name}”?", text, "Delete", do_delete)

    # --- name already in use: shake + bubble, nothing else

    def _show_name_error(self):
        self._close_name_error()
        tip = label("Name already in use", obj="nameError")
        tip.setParent(self)
        tip.adjustSize()
        pos = self.name_edit.mapTo(self, QPoint(0, 0))
        tip.move(pos.x(), pos.y() - tip.height() - 8)
        tip.show()
        tip.raise_()
        self._name_tip = tip
        self._tip_timer.start()

        anim = QVariantAnimation(self, startValue=0.0, endValue=1.0, duration=320)

        def step(t):
            off = int(round(math.sin(t * math.pi * 6) * 6 * (1 - t)))
            self.name_wrap.layout().setContentsMargins(6 + off, 0, 6 - off, 0)
        anim.valueChanged.connect(step)
        anim.finished.connect(lambda: self.name_wrap.layout().setContentsMargins(6, 0, 6, 0))
        anim.start(QVariantAnimation.DeleteWhenStopped)

    def _close_name_error(self):
        self._tip_timer.stop()
        if self._name_tip is not None:
            self._name_tip.deleteLater()
            self._name_tip = None

    # ------------------------------------------------------------------ dialogs

    def open_settings(self):
        ov = Overlay(self, "Settings", width=400)
        st = self.config.current_settings
        options = [
            ("dark_mode", "Dark mode", "Use the dark theme for this window.", self.apply_theme),
            ("autostart", "Launch with Windows", f"Start {APP_NAME} when you sign in.",
             lambda _v: self.config.sync_autostart_registry()),
            ("start_minimized", "Start minimized", "Open straight to the tray.", None),
            ("always_on_top", "Always on top",
             "Keep this window above a game running in borderless or windowed mode while you tune it.",
             self.set_topmost),
            ("close_to_tray", "Close to tray", "The X button hides the window instead of quitting.", None),
        ]
        for key, title, sub, action in options:
            row = QFrame(objectName="settingRow")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 10, 0, 10)
            rl.setSpacing(16)
            texts = QVBoxLayout()
            texts.setSpacing(2)
            texts.addWidget(QLabel(title))
            s = label(sub, role="sub")
            s.setWordWrap(True)
            texts.addWidget(s)
            rl.addLayout(texts, 1)
            sw = ToggleSwitch(bool(st.get(key)))

            def changed(v, k=key, a=action):
                self.config.update_setting(k, v)
                if a:
                    a(v)
            sw.toggled.connect(changed)
            rl.addWidget(sw, 0, Qt.AlignVCenter)
            ov.body.addWidget(row)
        where = self.config.app_dir if self.config.portable else f"{self.config.app_dir} (exe folder is read-only)"
        foot = label(f"Hotkeys and monitors are in the sidebar.\nSettings folder: {where}", role="note")
        foot.setWordWrap(True)
        ov.body.addSpacing(12)
        ov.body.addWidget(foot)

    def _confirm(self, title, text, action_label, on_confirm):
        ov = Overlay(self, title, width=380)
        msg = label(text, role="desc")
        msg.setWordWrap(True)
        msg.setStyleSheet("font-size: 13px;")
        ov.body.addSpacing(4)
        ov.body.addWidget(msg)
        ov.body.addSpacing(18)
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addStretch(1)
        cancel = button("Cancel", "outline")
        cancel.clicked.connect(ov.close_overlay)
        row.addWidget(cancel)
        ok = button(action_label, "danger")

        def go():
            ov.close_overlay()
            on_confirm()
        ok.clicked.connect(go)
        row.addWidget(ok)
        ov.body.addLayout(row)
        ok.setFocus()

    def apply_theme(self, dark):
        theme.set_theme(dark)
        QApplication.instance().setStyleSheet(theme.stylesheet())
        self.set_border_color(T["border2"])
        self.update_status_visuals()  # the Off dot colour depends on the theme
        self._refresh_icons()
        self.refresh_presets()
        if self.tab not in SLIDER_TABS:
            self._build_list_page(self.tab)
        for w in self.findChildren(QWidget):
            w.update()
        self._schedule_preview()

    # ------------------------------------------------------------------ filter

    def apply_filter(self):
        devices = self._selected_devices()
        self.gamma.apply_settings(self.draft, devices)
        nv = [d for d in devices if self._vib_ok.get(d)]
        if nv:
            self.vibrance.apply(self.draft.get("vibrance", vib.DEFAULT_PERCENT), nv)
        else:
            self.vibrance.restore()

    def restore_filter(self):
        self._apply_timer.stop()
        self.gamma.restore()
        self.vibrance.restore()

    def toggle_filter(self):
        self.filter_on = not self.filter_on
        if self.filter_on:
            self.apply_filter()
        else:
            self.restore_filter()
        self.update_status_visuals()

    def update_status_visuals(self):
        on = self.filter_on
        self.status_badge.setText(" On" if on else " Off")  # leading space = gap after the dot icon
        self.status_badge.setIcon(dot_icon(ACCENT if on else T["muted"]))
        set_prop(self.status_badge, "on", on)
        self.title_hk.setText(pretty_hotkey(self.config.current_settings.get("hotkey")))
        self.mon_summary.setText(self._monitor_summary())
        self.mon_dot.update()
        if self._layout_state.get("compact_nav"):
            self.mon_dot.setToolTip(self.mon_summary.text())
        self._schedule_preview()

    # ------------------------------------------------------------------ hotkeys

    def _set_hotkey(self, key, hotkey):
        """key None = the toggle hotkey, else a preset name."""
        if key is None:
            self.input_manager.update_main_hotkey(hotkey)
            self.update_status_visuals()
        else:
            self.input_manager.set_preset_hotkey(key, hotkey)
            self.refresh_presets()
        if key in self.hk_buttons:
            self.hk_buttons[key][1] = hotkey
        self.show_hotkey_status()

    def _record_hotkey_for(self, key):
        cap = self.hk_buttons[key][0]
        cap.setText("Press keys…")
        set_prop(cap, "state", "recording")
        cap.setFocus()

        def done(hotkey):
            if hotkey:
                self._set_hotkey(key, hotkey)
            else:
                self.input_manager.register_shortcuts()  # cancelled: re-register what we suspended
                self.show_hotkey_status()
        self.record_hotkey(done)

    def external_hotkey_status(self, failed):
        self.bridge.hotkey_status.emit(list(failed))

    def show_hotkey_status(self, failed=None):
        if failed is not None:
            self._failed_hotkeys = set(failed)
        for key, (cap, hotkey) in self.hk_buttons.items():
            try:
                bad = bool(hotkey) and hotkey in self._failed_hotkeys
                cap.setText(pretty_hotkey(hotkey) or "Not set")
                set_prop(cap, "state", "bad" if bad else "")
                set_prop(cap, "empty", not hotkey)
                cap.setToolTip("Not working: used by another app or invalid" if bad else "")
            except RuntimeError:
                pass  # page rebuilt meanwhile

    # --- Hotkey recording (Windows virtual-key codes from Qt's native key info)

    def record_hotkey(self, on_done):
        """Record a key combination. Finishes when all keys are released.
        Esc alone cancels; also cancels after 10s without input."""
        if self._rec is not None:
            return
        self.input_manager.suspend()
        timer = QTimer(self, singleShot=True, interval=10000, timeout=lambda: self._finish_recording(None))
        self._rec = {"pressed": set(), "mods": set(), "key": None, "on_done": on_done, "timer": timer}
        timer.start()
        QApplication.instance().installEventFilter(self)

    def eventFilter(self, obj, e):
        rec = self._rec
        if rec is None or e.type() not in (QEvent.KeyPress, QEvent.KeyRelease):
            return super().eventFilter(obj, e)
        vk = e.nativeVirtualKey()
        if e.type() == QEvent.KeyPress:
            if not e.isAutoRepeat() and vk:
                rec["pressed"].add(vk)
                if vk in MODIFIER_VKS:
                    rec["mods"].add(MODIFIER_VKS[vk])
                else:
                    rec["key"] = vk  # last non-modifier key wins (RegisterHotKey allows only one)
            return True
        if e.isAutoRepeat():
            return True
        rec["pressed"].discard(vk)
        if not rec["pressed"]:
            if rec["key"] is None:
                result = None  # modifiers only -> invalid
            elif rec["key"] == 0x1B and not rec["mods"]:
                result = None  # Esc alone -> cancel
            else:
                result = format_hotkey(rec["mods"], rec["key"])
                if not parse_hotkey(result):
                    result = None
            self._finish_recording(result)
        return True

    def _finish_recording(self, result):
        rec = self._rec
        if rec is None:
            return
        self._rec = None
        rec["timer"].stop()
        QApplication.instance().removeEventFilter(self)
        self.input_manager.is_recording = False
        # Callbacks re-register the hotkeys (update_*_hotkey / register_shortcuts)
        rec["on_done"](result)

    # ------------------------------------------------------------------ thread-safe external calls

    def external_toggle(self):
        self.bridge.toggle.emit()

    def external_load_preset(self, name):
        self.bridge.load_preset.emit(name)

    def external_show(self):
        self.bridge.show.emit()
