"""
Global hotkeys via the native Win32 RegisterHotKey API.

Why not a keyboard hook (the old `keyboard` library)?
Low-level keyboard hooks are silently removed by Windows when the hook
callback is too slow even once (LowLevelHooksTimeout), which tends to happen
after the PC has been idle / locked / under load for a while. Hotkeys
registered with RegisterHotKey are handled by Windows itself and never expire.

Hotkey strings keep the old format, e.g. "ctrl+f10", "alt+shift+n".
"""
import ctypes
import threading
from ctypes import wintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
user32.RegisterHotKey.restype = wintypes.BOOL
user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
user32.UnregisterHotKey.restype = wintypes.BOOL
user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = wintypes.BOOL
user32.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT]
user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostThreadMessageW.restype = wintypes.BOOL
user32.VkKeyScanW.argtypes = [wintypes.WCHAR]
user32.VkKeyScanW.restype = ctypes.c_short
user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
user32.MapVirtualKeyW.restype = wintypes.UINT

WM_HOTKEY = 0x0312
WM_APP = 0x8000
WM_APP_REREGISTER = WM_APP + 1
WM_APP_UNREGISTER = WM_APP + 2
PM_NOREMOVE = 0x0000
MAPVK_VK_TO_CHAR = 2

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

MODIFIER_NAMES = {
    "ctrl": MOD_CONTROL, "control": MOD_CONTROL,
    "alt": MOD_ALT,
    "shift": MOD_SHIFT,
    "windows": MOD_WIN, "win": MOD_WIN, "cmd": MOD_WIN,
}
MODIFIER_ORDER = ["ctrl", "alt", "shift", "windows"]

# Virtual-key codes of the modifier keys themselves (generic + left/right)
MODIFIER_VKS = {
    0x10: "shift", 0xA0: "shift", 0xA1: "shift",
    0x11: "ctrl", 0xA2: "ctrl", 0xA3: "ctrl",
    0x12: "alt", 0xA4: "alt", 0xA5: "alt",
    0x5B: "windows", 0x5C: "windows",
}

NAMED_KEYS = {
    "space": 0x20, "enter": 0x0D, "tab": 0x09, "esc": 0x1B, "escape": 0x1B,
    "backspace": 0x08, "insert": 0x2D, "delete": 0x2E, "home": 0x24, "end": 0x23,
    "page up": 0x21, "page down": 0x22,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "print screen": 0x2C, "pause": 0x13, "scroll lock": 0x91,
    "num lock": 0x90, "caps lock": 0x14,
    "num 0": 0x60, "num 1": 0x61, "num 2": 0x62, "num 3": 0x63, "num 4": 0x64,
    "num 5": 0x65, "num 6": 0x66, "num 7": 0x67, "num 8": 0x68, "num 9": 0x69,
    "num *": 0x6A, "num +": 0x6B, "num -": 0x6D, "num .": 0x6E, "num /": 0x6F,
}
for _i in range(1, 25):
    NAMED_KEYS[f"f{_i}"] = 0x6F + _i
# Aliases accepted when parsing old configs
NAMED_KEYS.update({"return": 0x0D, "pgup": 0x21, "pgdn": 0x22, "del": 0x2E, "ins": 0x2D})

_VK_TO_NAME = {}
for _name, _vk in NAMED_KEYS.items():
    _VK_TO_NAME.setdefault(_vk, _name)


def vk_to_name(vk):
    """Human/config-friendly name for a (non-modifier) virtual-key code."""
    if vk in _VK_TO_NAME:
        return _VK_TO_NAME[vk]
    if 0x30 <= vk <= 0x39 or 0x41 <= vk <= 0x5A:
        return chr(vk).lower()
    ch = user32.MapVirtualKeyW(vk, MAPVK_VK_TO_CHAR) & 0xFFFF
    if ch and chr(ch).isprintable() and chr(ch) != "+":
        return chr(ch).lower()
    return f"vk{vk:02x}"


def name_to_vk(name):
    name = name.strip().lower()
    if name in NAMED_KEYS:
        return NAMED_KEYS[name]
    if name.startswith("vk") and len(name) > 2:
        try:
            return int(name[2:], 16)
        except ValueError:
            return None
    if len(name) == 1:
        if name.isalnum() and name.isascii():
            return ord(name.upper())
        res = user32.VkKeyScanW(name)
        if res != -1:
            return res & 0xFF
    return None


def parse_hotkey(hotkey):
    """'ctrl+f10' -> (modifiers, vk) or None if invalid."""
    if not hotkey:
        return None
    mods = 0
    vk = None
    # Allow "+" itself as key: "ctrl++" -> ["ctrl", "+"]
    parts = hotkey.lower().split("+")
    tokens = []
    for i, p in enumerate(parts):
        if p == "" and i == len(parts) - 1 and tokens and tokens[-1] == "":
            tokens[-1] = "+"
        else:
            tokens.append(p)
    for tok in tokens:
        tok = tok.strip().replace("left ", "").replace("right ", "")
        if tok in MODIFIER_NAMES:
            mods |= MODIFIER_NAMES[tok]
        elif tok:
            if vk is not None:
                return None  # only one non-modifier key is allowed
            vk = name_to_vk(tok)
            if vk is None:
                return None
    if vk is None:
        return None
    return mods, vk


def format_hotkey(modifier_names, vk):
    mods = [m for m in MODIFIER_ORDER if m in modifier_names]
    return "+".join(mods + [vk_to_name(vk)])


class InputManager:
    def __init__(self, config_manager, toggle_callback, preset_callback=None):
        self.config = config_manager
        self.toggle_cb = toggle_callback
        self.preset_cb = preset_callback
        self.main_hotkey = self.config.current_settings.get("hotkey")
        self.is_recording = False

        self._thread_id = None
        self._ready = threading.Event()
        self._actions = {}  # hotkey id -> callable
        self._failed = []   # hotkeys that could not be registered (e.g. used by another app)
        self._status_cb = None  # called with the list of failed hotkeys after each registration

        threading.Thread(target=self._message_loop, daemon=True, name="HotkeyLoop").start()
        self._ready.wait(2.0)

    # --- Hotkey thread ---

    def _message_loop(self):
        msg = wintypes.MSG()
        # Force creation of this thread's message queue before anyone posts to it
        user32.PeekMessageW(ctypes.byref(msg), None, WM_APP, WM_APP, PM_NOREMOVE)
        self._thread_id = kernel32.GetCurrentThreadId()
        self._register_all()
        self._ready.set()

        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY:
                action = self._actions.get(int(msg.wParam))
                if action:
                    try:
                        action()
                    except Exception as e:
                        print(f"Hotkey action error: {e}")
            elif msg.message == WM_APP_REREGISTER:
                self._register_all()
            elif msg.message == WM_APP_UNREGISTER:
                self._unregister_all()

    def _unregister_all(self):
        for hk_id in list(self._actions.keys()):
            user32.UnregisterHotKey(None, hk_id)
        self._actions.clear()

    def _register_all(self):
        """Must run on the hotkey thread (RegisterHotKey binds to the calling thread)."""
        self._unregister_all()
        self._failed = []
        next_id = 1

        entries = []
        if self.main_hotkey:
            entries.append((self.main_hotkey, self._on_toggle))
        for name, data in self.config.presets.items():
            if isinstance(data, dict) and data.get("hotkey"):
                entries.append((data["hotkey"], lambda n=name: self._on_preset(n)))

        for hotkey, action in entries:
            parsed = parse_hotkey(hotkey)
            if not parsed:
                print(f"Invalid hotkey '{hotkey}'")
                self._failed.append(hotkey)
                continue
            mods, vk = parsed
            if user32.RegisterHotKey(None, next_id, mods | MOD_NOREPEAT, vk):
                self._actions[next_id] = action
                next_id += 1
            else:
                print(f"Failed to register hotkey '{hotkey}' (already used by another app?)")
                self._failed.append(hotkey)

        self._notify_status()

    def _notify_status(self):
        if self._status_cb:
            try:
                self._status_cb(list(self._failed))
            except Exception as e:
                print(f"Hotkey status callback error: {e}")

    def _post(self, message):
        if self._thread_id:
            user32.PostThreadMessageW(self._thread_id, message, 0, 0)

    # --- Public API (any thread) ---

    def set_status_callback(self, callback):
        """callback(failed_hotkeys: list[str]) — called from the hotkey thread."""
        self._status_cb = callback
        self._notify_status()

    def register_shortcuts(self):
        """(Re)register main + preset hotkeys."""
        if self.is_recording:
            return
        self._post(WM_APP_REREGISTER)

    def suspend(self):
        """Temporarily disable all hotkeys (used while recording a new one)."""
        self.is_recording = True
        self._post(WM_APP_UNREGISTER)

    def resume(self):
        self.is_recording = False
        self.register_shortcuts()

    def _on_toggle(self):
        if self.toggle_cb:
            self.toggle_cb()

    def _on_preset(self, preset_name):
        if self.preset_cb:
            self.preset_cb(preset_name)

    def update_main_hotkey(self, new_hotkey):
        """Set (or with None/"" remove) the toggle hotkey."""
        self.main_hotkey = new_hotkey or None
        self.config.update_setting("hotkey", self.main_hotkey)
        self.register_shortcuts()

    def set_preset_hotkey(self, preset_name, new_hotkey):
        if preset_name in self.config.presets:
            self.config.presets[preset_name]["hotkey"] = new_hotkey
            self.config.save_presets()
            self.register_shortcuts()
