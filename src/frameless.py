"""
Borderless window that still behaves like a native Windows 11 window.

The window keeps the native styles (caption, thick frame, min/max box) so Windows
itself handles moving, resizing, Aero Snap, Snap Layouts (hover on maximize),
the minimize/maximize animations, the shadow and the rounded corners.
Two messages are intercepted:
  WM_NCCALCSIZE  -> the whole window is client area (no native title bar is drawn)
  WM_NCHITTEST   -> tells Windows where the resize edges, the caption and the
                    maximize button of our own title bar are
"""
import ctypes
from ctypes import wintypes

from PySide6.QtCore import Qt, QPoint
from PySide6.QtWidgets import QWidget, QAbstractButton

user32 = ctypes.windll.user32
dwmapi = ctypes.windll.dwmapi

user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
user32.GetSystemMetricsForDpi.argtypes = [ctypes.c_int, wintypes.UINT]
user32.GetDpiForWindow.argtypes = [wintypes.HWND]
user32.IsZoomed.argtypes = [wintypes.HWND]
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, wintypes.UINT]

GWL_STYLE = -16
WS_CAPTION, WS_THICKFRAME, WS_SYSMENU = 0x00C00000, 0x00040000, 0x00080000
WS_MINIMIZEBOX, WS_MAXIMIZEBOX = 0x00020000, 0x00010000
SWP_FRAMECHANGED, SWP_NOMOVE, SWP_NOSIZE, SWP_NOZORDER, SWP_NOACTIVATE = 0x20, 0x2, 0x1, 0x4, 0x10
HWND_TOPMOST, HWND_NOTOPMOST = -1, -2

WM_NCCALCSIZE, WM_NCHITTEST = 0x0083, 0x0084
WM_NCMOUSEMOVE, WM_NCLBUTTONDOWN, WM_NCLBUTTONUP, WM_NCMOUSELEAVE = 0x00A0, 0x00A1, 0x00A2, 0x02A2
HTCLIENT, HTCAPTION, HTMAXBUTTON = 1, 2, 9
HTLEFT, HTRIGHT, HTTOP, HTTOPLEFT, HTTOPRIGHT, HTBOTTOM, HTBOTTOMLEFT, HTBOTTOMRIGHT = 10, 11, 12, 13, 14, 15, 16, 17
SM_CXSIZEFRAME, SM_CYSIZEFRAME, SM_CXPADDEDBORDER = 32, 33, 92
DWMWA_WINDOW_CORNER_PREFERENCE, DWMWA_BORDER_COLOR = 33, 34
RESIZE_BORDER = 6  # logical px


class NCCALCSIZE_PARAMS(ctypes.Structure):
    _fields_ = [("rgrc", wintypes.RECT * 3), ("lppos", ctypes.c_void_p)]


class FramelessWindow(QWidget):
    """Subclasses set `self.title_bar` (a QWidget at the top) and `self.max_button`."""

    def __init__(self):
        super().__init__(None, Qt.Window | Qt.FramelessWindowHint | Qt.WindowMinMaxButtonsHint)
        self.title_bar = None
        self.max_button = None
        self._max_hot = False
        self._hwnd = int(self.winId())
        style = user32.GetWindowLongPtrW(self._hwnd, GWL_STYLE)
        user32.SetWindowLongPtrW(self._hwnd, GWL_STYLE, style | WS_CAPTION | WS_THICKFRAME | WS_SYSMENU
                                 | WS_MINIMIZEBOX | WS_MAXIMIZEBOX)
        user32.SetWindowPos(self._hwnd, None, 0, 0, 0, 0,
                            SWP_FRAMECHANGED | SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)
        self._dwm_int(DWMWA_WINDOW_CORNER_PREFERENCE, 2)  # DWMWCP_ROUND (Windows 11)

    # --- helpers

    def _dwm_int(self, attr, value):
        try:
            v = ctypes.c_uint(value)
            dwmapi.DwmSetWindowAttribute(wintypes.HWND(self._hwnd), attr, ctypes.byref(v), 4)
        except Exception:
            pass

    def set_border_color(self, hex_color):
        r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
        self._dwm_int(DWMWA_BORDER_COLOR, r | (g << 8) | (b << 16))

    def set_topmost(self, on):
        user32.SetWindowPos(self._hwnd, HWND_TOPMOST if on else HWND_NOTOPMOST, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)

    def toggle_maximize(self):
        self.showNormal() if self.isMaximized() else self.showMaximized()

    def _set_max_hot(self, hot):
        if self.max_button is not None and hot != self._max_hot:
            self._max_hot = hot
            self.max_button.setProperty("hot", hot)
            self.max_button.style().unpolish(self.max_button)
            self.max_button.style().polish(self.max_button)

    def _hit_title_bar(self, pos):
        """pos in window coordinates -> HTCAPTION, HTMAXBUTTON or HTCLIENT."""
        if self.title_bar is None or not self.title_bar.geometry().contains(pos):
            return None
        local = self.title_bar.mapFrom(self, pos)
        w = self.title_bar.childAt(local)
        if w is not None and self.max_button is not None and (w is self.max_button or self.max_button.isAncestorOf(w)):
            return HTMAXBUTTON
        while w is not None and w is not self.title_bar:
            if isinstance(w, QAbstractButton):
                return HTCLIENT
            w = w.parentWidget()
        return HTCAPTION

    # --- native messages

    def nativeEvent(self, event_type, message):
        if bytes(event_type) != b"windows_generic_MSG":
            return super().nativeEvent(event_type, message)
        msg = wintypes.MSG.from_address(int(message))

        if msg.message == WM_NCCALCSIZE and msg.wParam:
            if user32.IsZoomed(msg.hWnd):
                # a maximized window is placed past the screen edge by its frame size: pull it back in
                dpi = user32.GetDpiForWindow(msg.hWnd)
                pad = user32.GetSystemMetricsForDpi(SM_CXPADDEDBORDER, dpi)
                fx = user32.GetSystemMetricsForDpi(SM_CXSIZEFRAME, dpi) + pad
                fy = user32.GetSystemMetricsForDpi(SM_CYSIZEFRAME, dpi) + pad
                params = NCCALCSIZE_PARAMS.from_address(msg.lParam)
                r = params.rgrc[0]
                r.left += fx
                r.top += fy
                r.right -= fx
                r.bottom -= fy
            return True, 0

        if msg.message == WM_NCHITTEST:
            x = ctypes.c_short(msg.lParam & 0xFFFF).value
            y = ctypes.c_short((msg.lParam >> 16) & 0xFFFF).value
            rect = wintypes.RECT()
            user32.GetWindowRect(msg.hWnd, ctypes.byref(rect))
            dpr = self.devicePixelRatioF()
            lx, ly = x - rect.left, y - rect.top
            w, h = rect.right - rect.left, rect.bottom - rect.top
            if not user32.IsZoomed(msg.hWnd):
                b = int(RESIZE_BORDER * dpr)
                left, right, top, bottom = lx < b, lx >= w - b, ly < b, ly >= h - b
                edge = {(True, False, True, False): HTTOPLEFT, (False, True, True, False): HTTOPRIGHT,
                        (True, False, False, True): HTBOTTOMLEFT, (False, True, False, True): HTBOTTOMRIGHT,
                        (True, False, False, False): HTLEFT, (False, True, False, False): HTRIGHT,
                        (False, False, True, False): HTTOP, (False, False, False, True): HTBOTTOM}.get(
                    (left, right, top, bottom))
                if edge:
                    self._set_max_hot(False)
                    return True, edge
            hit = self._hit_title_bar(QPoint(int(lx / dpr), int(ly / dpr)))
            self._set_max_hot(hit == HTMAXBUTTON)
            if hit is not None:
                return True, hit
            return True, HTCLIENT

        # The maximize button is reported as HTMAXBUTTON (for Snap Layouts), so its
        # mouse events arrive as non-client messages: drive the Qt button from them.
        if msg.message == WM_NCMOUSEMOVE:
            self._set_max_hot(msg.wParam == HTMAXBUTTON)
        elif msg.message == WM_NCMOUSELEAVE:
            self._set_max_hot(False)
        elif msg.message == WM_NCLBUTTONDOWN and msg.wParam == HTMAXBUTTON:
            return True, 0
        elif msg.message == WM_NCLBUTTONUP and msg.wParam == HTMAXBUTTON:
            self._set_max_hot(False)
            self.toggle_maximize()
            return True, 0
        return super().nativeEvent(event_type, message)
