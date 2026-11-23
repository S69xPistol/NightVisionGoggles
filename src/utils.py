import sys
import os
import ctypes
from ctypes import wintypes

APP_NAME = "NightVision"
APP_USER_MODEL_ID = "NightVision.FilterTool"

# Windows API for Mutex
kernel32 = ctypes.windll.kernel32
user32 = ctypes.windll.user32
CreateMutexW = kernel32.CreateMutexW
CloseHandle = kernel32.CloseHandle
GetLastError = kernel32.GetLastError
ERROR_ALREADY_EXISTS = 183

class SingleInstance:
    """
    Ensures only one instance of the application is running using a named Mutex.
    """
    def __init__(self, name="Global\\NightVision_Single_Instance_Mutex"):
        self.mutex_name = name
        self.mutex_handle = None
        self.is_already_running = False

    def check(self):
        self.mutex_handle = CreateMutexW(None, False, self.mutex_name)
        if not self.mutex_handle:
            # Should rarely happen unless system is very unstable
            return True

        if GetLastError() == ERROR_ALREADY_EXISTS:
            self.is_already_running = True
            return True

        return False

    def release(self):
        if self.mutex_handle:
            CloseHandle(self.mutex_handle)
            self.mutex_handle = None

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    return os.path.join(base_path, relative_path)

def get_app_dir():
    """Returns the directory where the executable or script is located."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    # If running from src/main.py, we want the project root (parent of src)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def set_app_user_model_id():
    """Give the process its own taskbar identity, so Windows shows our icon
    instead of the python.exe / Tk one."""
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:
        pass


# --- Monitor helpers ---

class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_int), ("top", ctypes.c_int), ("right", ctypes.c_int), ("bottom", ctypes.c_int)]

class MONITORINFOEX(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_int),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", ctypes.c_int),
        ("szDevice", ctypes.c_wchar * 32)
    ]

MonitorEnumProc = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(RECT), ctypes.c_int)

def get_primary_display_name():
    """Returns the GDI device name of the primary monitor, e.g. '\\\\.\\DISPLAY1'."""
    primary_name = []

    def callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
        mon_info = MONITORINFOEX()
        mon_info.cbSize = ctypes.sizeof(MONITORINFOEX)
        if ctypes.windll.user32.GetMonitorInfoW(ctypes.c_void_p(hMonitor), ctypes.byref(mon_info)):
            if mon_info.dwFlags & 1:  # MONITORINFOF_PRIMARY
                primary_name.append(mon_info.szDevice)
                return 0
        return 1

    ctypes.windll.user32.EnumDisplayMonitors(None, None, MonitorEnumProc(callback), 0)
    return primary_name[0] if primary_name else None


def get_work_area(hwnd):
    """Work area (screen minus taskbar) of the monitor a window is on: (x, y, w, h)."""
    hmon = user32.MonitorFromWindow(wintypes.HWND(hwnd), 2)  # MONITOR_DEFAULTTONEAREST
    info = MONITORINFOEX()
    info.cbSize = ctypes.sizeof(MONITORINFOEX)
    if hmon and user32.GetMonitorInfoW(ctypes.c_void_p(hmon), ctypes.byref(info)):
        r = info.rcWork
        return r.left, r.top, r.right - r.left, r.bottom - r.top
    return 0, 0, user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


class DISPLAY_DEVICEW(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("DeviceName", ctypes.c_wchar * 32),
                ("DeviceString", ctypes.c_wchar * 128), ("StateFlags", wintypes.DWORD),
                ("DeviceID", ctypes.c_wchar * 128), ("DeviceKey", ctypes.c_wchar * 128)]

class DEVMODEW(ctypes.Structure):
    _fields_ = [("dmDeviceName", ctypes.c_wchar * 32), ("dmSpecVersion", wintypes.WORD),
                ("dmDriverVersion", wintypes.WORD), ("dmSize", wintypes.WORD),
                ("dmDriverExtra", wintypes.WORD), ("dmFields", wintypes.DWORD),
                ("dmPositionX", ctypes.c_long), ("dmPositionY", ctypes.c_long),
                ("dmDisplayOrientation", wintypes.DWORD), ("dmDisplayFixedOutput", wintypes.DWORD),
                ("dmColor", ctypes.c_short), ("dmDuplex", ctypes.c_short),
                ("dmYResolution", ctypes.c_short), ("dmTTOption", ctypes.c_short),
                ("dmCollate", ctypes.c_short), ("dmFormName", ctypes.c_wchar * 32),
                ("dmLogPixels", wintypes.WORD), ("dmBitsPerPel", wintypes.DWORD),
                ("dmPelsWidth", wintypes.DWORD), ("dmPelsHeight", wintypes.DWORD),
                ("dmDisplayFlags", wintypes.DWORD), ("dmDisplayFrequency", wintypes.DWORD),
                ("dmICMMethod", wintypes.DWORD), ("dmICMIntent", wintypes.DWORD),
                ("dmMediaType", wintypes.DWORD), ("dmDitherType", wintypes.DWORD),
                ("dmReserved1", wintypes.DWORD), ("dmReserved2", wintypes.DWORD),
                ("dmPanningWidth", wintypes.DWORD), ("dmPanningHeight", wintypes.DWORD)]

# DisplayConfig structures, only used to read the monitors' friendly names (EDID)
class LUID(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", ctypes.c_long)]

class DISPLAYCONFIG_PATH_INFO(ctypes.Structure):
    _fields_ = [("src_adapter", LUID), ("src_id", ctypes.c_uint32), ("src_mode_idx", ctypes.c_uint32),
                ("src_flags", ctypes.c_uint32),
                ("tgt_adapter", LUID), ("tgt_id", ctypes.c_uint32), ("tgt_mode_idx", ctypes.c_uint32),
                ("tgt_tech", ctypes.c_uint32), ("tgt_rotation", ctypes.c_uint32), ("tgt_scaling", ctypes.c_uint32),
                ("tgt_refresh_num", ctypes.c_uint32), ("tgt_refresh_den", ctypes.c_uint32),
                ("tgt_scanline", ctypes.c_uint32), ("tgt_available", wintypes.BOOL), ("tgt_flags", ctypes.c_uint32),
                ("flags", ctypes.c_uint32)]

class DISPLAYCONFIG_DEVICE_INFO_HEADER(ctypes.Structure):
    _fields_ = [("type", ctypes.c_uint32), ("size", ctypes.c_uint32), ("adapterId", LUID), ("id", ctypes.c_uint32)]

class DISPLAYCONFIG_SOURCE_DEVICE_NAME(ctypes.Structure):
    _fields_ = [("header", DISPLAYCONFIG_DEVICE_INFO_HEADER), ("viewGdiDeviceName", ctypes.c_wchar * 32)]

class DISPLAYCONFIG_TARGET_DEVICE_NAME(ctypes.Structure):
    _fields_ = [("header", DISPLAYCONFIG_DEVICE_INFO_HEADER), ("flags", ctypes.c_uint32),
                ("outputTechnology", ctypes.c_uint32), ("edidManufactureId", ctypes.c_uint16),
                ("edidProductCodeId", ctypes.c_uint16), ("connectorInstance", ctypes.c_uint32),
                ("monitorFriendlyDeviceName", ctypes.c_wchar * 64), ("monitorDevicePath", ctypes.c_wchar * 128)]


def _friendly_monitor_names():
    """{'\\\\.\\DISPLAY1': 'ASUS VG27AQ', ...} from the monitors' EDID. Empty on failure."""
    names = {}
    try:
        n_paths, n_modes = ctypes.c_uint32(), ctypes.c_uint32()
        QDC_ONLY_ACTIVE_PATHS = 2
        if user32.GetDisplayConfigBufferSizes(QDC_ONLY_ACTIVE_PATHS, ctypes.byref(n_paths), ctypes.byref(n_modes)):
            return names
        paths = (DISPLAYCONFIG_PATH_INFO * n_paths.value)()
        modes = (ctypes.c_byte * (64 * max(1, n_modes.value)))()  # DISPLAYCONFIG_MODE_INFO is 64 bytes
        if user32.QueryDisplayConfig(QDC_ONLY_ACTIVE_PATHS, ctypes.byref(n_paths), paths,
                                     ctypes.byref(n_modes), modes, None):
            return names
        for p in paths[:n_paths.value]:
            src = DISPLAYCONFIG_SOURCE_DEVICE_NAME()
            src.header.type, src.header.size = 1, ctypes.sizeof(src)  # GET_SOURCE_NAME
            src.header.adapterId, src.header.id = p.src_adapter, p.src_id
            tgt = DISPLAYCONFIG_TARGET_DEVICE_NAME()
            tgt.header.type, tgt.header.size = 2, ctypes.sizeof(tgt)  # GET_TARGET_NAME
            tgt.header.adapterId, tgt.header.id = p.tgt_adapter, p.tgt_id
            if (user32.DisplayConfigGetDeviceInfo(ctypes.byref(src)) == 0 and
                    user32.DisplayConfigGetDeviceInfo(ctypes.byref(tgt)) == 0 and tgt.monitorFriendlyDeviceName):
                names[src.viewGdiDeviceName] = tgt.monitorFriendlyDeviceName
    except Exception as e:
        print(f"Could not read monitor names: {e}")
    return names


def enumerate_monitors():
    """Active monitors, primary first:
    [{'device': '\\\\.\\DISPLAY1', 'name': 'ASUS VG27AQ', 'gpu': 'NVIDIA GeForce ...',
      'width': 2560, 'height': 1440, 'refresh': 165, 'primary': True}, ...]"""
    friendly = _friendly_monitor_names()
    monitors = []
    i = 0
    while True:
        dd = DISPLAY_DEVICEW()
        dd.cb = ctypes.sizeof(dd)
        if not user32.EnumDisplayDevicesW(None, i, ctypes.byref(dd), 0):
            break
        i += 1
        if not dd.StateFlags & 0x1:  # DISPLAY_DEVICE_ATTACHED_TO_DESKTOP
            continue
        mon = DISPLAY_DEVICEW()
        mon.cb = ctypes.sizeof(mon)
        mon_name = mon.DeviceString if user32.EnumDisplayDevicesW(dd.DeviceName, 0, ctypes.byref(mon), 0) else ""
        dm = DEVMODEW()
        dm.dmSize = ctypes.sizeof(dm)
        has_mode = user32.EnumDisplaySettingsW(dd.DeviceName, -1, ctypes.byref(dm))  # ENUM_CURRENT_SETTINGS
        monitors.append({
            "device": dd.DeviceName,
            "name": friendly.get(dd.DeviceName) or mon_name or dd.DeviceName.replace("\\\\.\\", ""),
            "gpu": dd.DeviceString,
            "width": dm.dmPelsWidth if has_mode else 0,
            "height": dm.dmPelsHeight if has_mode else 0,
            "refresh": dm.dmDisplayFrequency if has_mode else 0,
            "primary": bool(dd.StateFlags & 0x4),  # DISPLAY_DEVICE_PRIMARY_DEVICE
        })
    monitors.sort(key=lambda m: (not m["primary"], m["device"]))
    return monitors
