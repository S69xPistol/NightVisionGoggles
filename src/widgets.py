"""Small custom widgets used by the main window (painted with the active theme in theme.T)."""
from PySide6.QtCore import Qt, Signal, QRectF, QPointF, QSize, QVariantAnimation, QEasingCurve, QTimer, QEvent
from PySide6.QtGui import QPainter, QColor, QPen, QPainterPath, QIcon, QPixmap, QFont, QImage
from PySide6.QtWidgets import (QAbstractButton, QSlider, QLabel, QPushButton, QWidget, QFrame, QHBoxLayout,
                               QVBoxLayout, QToolButton, QSizePolicy, QStyle, QStyleOptionSlider)

from . import theme
from .theme import T, G, FONTS, ACCENT


def polish(widget):
    """Re-apply the stylesheet after a dynamic property changed."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def set_prop(widget, name, value):
    if widget.property(name) != value:
        widget.setProperty(name, value)
        polish(widget)


def glyph_icon(glyph, color, px=14, box=16):
    """QIcon from a Segoe Fluent Icons glyph (sharp at any DPI: drawn at 2x)."""
    scale = 2
    pm = QPixmap(box * scale, box * scale)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)
    f = QFont(FONTS["icon"])
    f.setPixelSize(px * scale)
    p.setFont(f)
    p.setPen(QColor(color))
    p.drawText(pm.rect(), Qt.AlignCenter, glyph)
    p.end()
    pm.setDevicePixelRatio(scale)
    return QIcon(pm)


def dot_icon(color, d=8):
    """Filled circle as an icon (a '●' character sits too low next to text)."""
    scale = 2
    pm = QPixmap(d * scale, d * scale)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    p.drawEllipse(pm.rect())
    p.end()
    pm.setDevicePixelRatio(scale)
    return QIcon(pm)


def glyph_label(glyph, px=14, color=None):
    """Icon as a label (the app stylesheet would override setFont, so style it inline)."""
    lbl = QLabel(glyph)
    lbl.setStyleSheet(f'font-family: "{FONTS["icon"]}"; font-size: {px}px; background: transparent;'
                      + (f" color: {color};" if color else ""))
    return lbl


def separator(vertical=False):
    line = QFrame()
    line.setProperty("sep", True)
    if vertical:
        line.setFixedWidth(1)
    else:
        line.setFixedHeight(1)
    return line


class Dot(QWidget):
    """A small filled circle (status dots)."""
    def __init__(self, color, size=7, parent=None):
        super().__init__(parent)
        self._color = color
        self.setFixedSize(size, size)

    def set_color(self, color):
        self._color = color
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(self._color() if callable(self._color) else self._color))
        p.drawEllipse(self.rect())


class ToggleSwitch(QAbstractButton):
    """Windows-11-like switch, 40x22, animated knob."""
    def __init__(self, checked=False, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(40, 22)
        self._pos = 1.0 if checked else 0.0
        self._anim = QVariantAnimation(self, duration=140, easingCurve=QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._set_pos)
        self.toggled.connect(self._animate)

    def _set_pos(self, v):
        self._pos = float(v)
        self.update()

    def _animate(self, on):
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        on = self.isChecked()
        p.setPen(QPen(QColor(ACCENT if on else T["faint"]), 1))
        p.setBrush(QColor(ACCENT) if on else Qt.NoBrush)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        d = 14 if (on or self.underMouse()) else 12
        x = 4 + self._pos * (self.width() - 8 - 14) + (14 - d) / 2
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(theme.ON_ACCENT if on else T["muted"]))
        p.drawEllipse(QRectF(x, (self.height() - d) / 2, d, d))

    def enterEvent(self, e):
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.update()
        super().leaveEvent(e)


class CheckBox(QAbstractButton):
    """18x18 rounded checkbox with a drawn check mark."""
    def __init__(self, checked=False, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(18, 18)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.75, 0.75, -0.75, -0.75)
        if self.isChecked():
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(ACCENT))
            p.drawRoundedRect(r, 4, 4)
            pen = QPen(QColor(theme.ON_ACCENT), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            p.setPen(pen)
            path = QPainterPath(QPointF(4.5, 9.2))
            path.lineTo(7.7, 12.3)
            path.lineTo(13.5, 5.8)
            p.drawPath(path)
        else:
            p.setPen(QPen(QColor(T["faint"]), 1.5))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(r, 4, 4)


class ValueSlider(QSlider):
    """Horizontal slider on a float range, with a tick at the default value."""
    valueChangedF = Signal(float)
    reset = Signal()

    def __init__(self, lo, hi, step, default, channel=None, parent=None):
        super().__init__(Qt.Horizontal, parent)
        self.lo, self.hi, self.step_size, self.default = lo, hi, step, default
        self.setRange(0, max(1, round((hi - lo) / step)))
        self.setPageStep(max(1, self.maximum() // 10))
        self.setCursor(Qt.PointingHandCursor)
        if channel:
            self.setProperty("channel", channel)
        self.valueChanged.connect(lambda v: self.valueChangedF.emit(self.to_float(v)))

    def to_float(self, v):
        return round(self.lo + v * self.step_size, 4)

    def set_float(self, value):
        self.blockSignals(True)
        self.setValue(round((float(value) - self.lo) / self.step_size))
        self.blockSignals(False)

    def mousePressEvent(self, e):
        # Jump straight to the clicked position (Windows sliders do this; Qt pages by default)
        if e.button() == Qt.LeftButton:
            opt = QStyleOptionSlider()
            self.initStyleOption(opt)
            handle = self.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderHandle, self)
            if not handle.contains(e.position().toPoint()):
                half = handle.width() / 2
                frac = (e.position().x() - half) / max(1, self.width() - handle.width())
                self.setValue(round(min(1, max(0, frac)) * self.maximum()))
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e):
        self.reset.emit()

    def paintEvent(self, e):
        # default tick first, so the groove and the handle are drawn over it
        frac = (self.default - self.lo) / (self.hi - self.lo)
        x = 8 + frac * (self.width() - 16)
        p = QPainter(self)
        p.setPen(QPen(QColor(T["faint"]), 1))
        cy = self.height() / 2
        p.drawLine(QPointF(x, cy - 7), QPointF(x, cy + 7))
        p.end()
        super().paintEvent(e)


class ClickLabel(QLabel):
    doubleClicked = Signal()
    clicked = Signal()

    def mouseDoubleClickEvent(self, e):
        self.doubleClicked.emit()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(e)


class ElidedLabel(QLabel):
    """Label that shortens its text with '…' to the space it gets."""
    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self._full = text
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setMinimumWidth(20)
        self._refresh()

    def setFullText(self, text):
        self._full = text
        self._refresh()

    def fullText(self):
        return self._full

    def is_elided(self):
        return self.text() != self._full

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._refresh()

    def changeEvent(self, e):
        super().changeEvent(e)
        if e.type() in (QEvent.FontChange, QEvent.StyleChange):
            self._refresh()

    def _refresh(self):
        text = self.fontMetrics().elidedText(self._full, Qt.ElideRight, max(10, self.width()))
        if text != self.text():
            self.setText(text)
        self.setToolTip(self._full if text != self._full else "")


class NavButton(QPushButton):
    """Sidebar entry: icon + label, accent bar on the left when selected."""
    def __init__(self, glyph, label, parent=None):
        super().__init__(label, parent)
        self.glyph, self.label = glyph, label
        self.setProperty("kind", "nav")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setIconSize(QSize(16, 16))
        self.refresh_icon()

    def refresh_icon(self):
        icon = glyph_icon(self.glyph, T["muted"], 15)
        icon.addPixmap(glyph_icon(self.glyph, ACCENT, 15).pixmap(16, 16), QIcon.Normal, QIcon.On)
        self.setIcon(icon)

    def set_compact(self, compact):
        self.setText("" if compact else f"  {self.label}")
        self.setToolTip(self.label if compact else "")
        self.setStyleSheet("padding: 0; text-align: center;" if compact else "")

    def paintEvent(self, e):
        super().paintEvent(e)
        if self.isChecked():
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(ACCENT))
            p.drawRoundedRect(QRectF(0, 10, 3, self.height() - 20), 1.5, 1.5)


class PresetRow(QFrame):
    """One preset in the right sidebar: [lock] name ● hotkey [trash]."""
    clicked = Signal(str)
    deleteRequested = Signal(str)

    def __init__(self, name, hotkey_text, locked, parent=None):
        super().__init__(parent)
        self.name = name
        self.setObjectName("presetRow")
        self.setAttribute(Qt.WA_Hover)
        self.setAttribute(Qt.WA_StyledBackground)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(38)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 4 if not locked else 10, 0)
        lay.setSpacing(8)
        if locked:
            lay.addWidget(glyph_label(G["lock"], 12, T["faint"]))
        self.name_lbl = ElidedLabel(name)
        self.name_lbl.setObjectName("presetName")
        lay.addWidget(self.name_lbl, 1)
        self.dot = Dot(ACCENT)
        self.dot.hide()
        lay.addWidget(self.dot)
        self.hk_lbl = QLabel(hotkey_text)
        self.hk_lbl.setProperty("mono", True)
        self.hk_lbl.setProperty("role", "hk")
        lay.addWidget(self.hk_lbl)
        if not locked:
            trash = QToolButton()
            trash.setText(G["trash"])
            trash.setProperty("kind", "trash")
            trash.setToolTip("Delete preset")
            trash.setCursor(Qt.PointingHandCursor)
            trash.clicked.connect(lambda: self.deleteRequested.emit(self.name))
            lay.addWidget(trash)

    def set_selected(self, selected):
        set_prop(self, "selected", selected)
        polish(self.name_lbl)

    def set_dirty(self, dirty):
        self.dot.setVisible(dirty)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit(self.name)


class PreviewWidget(QWidget):
    """Shows a QImage with rounded corners and a 1px border, 'cover'-scaled."""
    resized = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._image = None
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(160, 100)

    def set_image(self, image: QImage):
        self._image = image
        self.update()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.resized.emit()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(r, 6, 6)
        p.setClipPath(path)
        if self._image is not None:
            p.drawImage(QRectF(self.rect()), self._image)
        p.setClipping(False)
        p.setPen(QPen(QColor(T["border"]), 1))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)


class Overlay(QWidget):
    """In-window modal: dims the window and centres a card, like the mockup's dialogs."""
    closed = Signal()

    def __init__(self, host: QWidget, title, width=400):
        super().__init__(host)
        self.setAttribute(Qt.WA_StyledBackground)
        self.setFocusPolicy(Qt.StrongFocus)
        self.card = QFrame(self)
        self.card.setObjectName("dialogCard")
        self.card.setFixedWidth(width)
        lay = QVBoxLayout(self.card)
        lay.setContentsMargins(20, 14, 12, 16)
        lay.setSpacing(0)
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 4)
        title_lbl = QLabel(title)
        title_lbl.setObjectName("dialogTitle")
        head.addWidget(title_lbl, 1)
        close = QPushButton()
        close.setProperty("kind", "glyph")
        close.setFixedSize(32, 32)
        close.setCursor(Qt.PointingHandCursor)
        close.setIcon(glyph_icon(G["x"], T["text2"], 11, 12))
        close.clicked.connect(self.close_overlay)
        head.addWidget(close)
        lay.addLayout(head)
        self.body = QVBoxLayout()
        self.body.setContentsMargins(0, 0, 8, 0)
        self.body.setSpacing(0)
        lay.addLayout(self.body)
        # Centre the card with a layout so its height follows the (word-wrapped) content
        self.card.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Maximum)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.addStretch(1)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.card)
        row.addStretch(1)
        outer.addLayout(row)
        outer.addStretch(1)
        host.installEventFilter(self)
        self.setGeometry(host.rect())
        self.show()
        self.raise_()
        self.setFocus()

    def eventFilter(self, obj, e):
        if e.type() == QEvent.Resize:
            self.setGeometry(obj.rect())
        return False

    def paintEvent(self, _e):
        p = QPainter(self)
        c = T["overlay"]
        nums = [int(v) for v in c[c.index("(") + 1:-1].split(",")]
        p.fillRect(self.rect(), QColor(*nums))

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close_overlay()
        else:
            super().keyPressEvent(e)

    def mousePressEvent(self, e):
        e.accept()  # clicks on the dimmed area don't reach the window below

    def close_overlay(self):
        self.parent().removeEventFilter(self)
        self.closed.emit()
        self.deleteLater()
