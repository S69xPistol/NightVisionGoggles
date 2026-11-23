"""
NVIDIA Digital Vibrance control via NVAPI (nvapi64.dll / nvapi.dll), loaded with ctypes.

The setting stored by NightVision is the NVIDIA Control Panel percentage
(0..100, driver default 50).

Two NVAPI flavours exist:
  - DVC "Ex" calls (NvAPI_GetDVCInfoEx / NvAPI_SetDVCLevelEx): the level IS the
    Control Panel percentage, 0..100 with default 50. Used whenever available.
  - legacy DVC calls (the ones vibranceGUI uses): level 0 = 50% and
    maxLevel (63) = 100%, so they cannot go below the default. Fallback only.

Vibrance is per display: every monitor driven by the NVIDIA card has its own level.
On non-NVIDIA systems `available` is False and every call is a no-op.
"""
import ctypes
from ctypes import Structure, c_int, c_uint, c_void_p, byref, sizeof, POINTER, CFUNCTYPE

from .utils import get_primary_display_name

NVAPI_OK = 0

# nvapi_QueryInterface function IDs
_ID_INITIALIZE = 0x0150E828
_ID_ENUM_NV_DISPLAY_HANDLE = 0x9ABDD40D
_ID_GET_ASSOCIATED_NV_DISPLAY_HANDLE = 0x35C29134
_ID_GET_DVC_INFO = 0x4085DE45
_ID_SET_DVC_LEVEL = 0x172409B4
_ID_GET_DVC_INFO_EX = 0x0E45002D
_ID_SET_DVC_LEVEL_EX = 0x4A82C2B1

MIN_PERCENT = 0
MAX_PERCENT = 100
DEFAULT_PERCENT = 50


class NV_DISPLAY_DVC_INFO(Structure):
    _fields_ = [
        ("version", c_uint),
        ("currentLevel", c_int),
        ("minLevel", c_int),
        ("maxLevel", c_int),
    ]


class NV_DISPLAY_DVC_INFO_EX(Structure):
    _fields_ = [
        ("version", c_uint),
        ("currentLevel", c_int),
        ("minLevel", c_int),
        ("maxLevel", c_int),
        ("defaultLevel", c_int),
    ]


_DVC_INFO_VER = sizeof(NV_DISPLAY_DVC_INFO) | (1 << 16)
_DVC_INFO_EX_VER = sizeof(NV_DISPLAY_DVC_INFO_EX) | (1 << 16)

_Initialize_t = CFUNCTYPE(c_int)
_EnumNvidiaDisplayHandle_t = CFUNCTYPE(c_int, c_int, POINTER(c_void_p))
_GetAssociatedNvidiaDisplayHandle_t = CFUNCTYPE(c_int, ctypes.c_char_p, POINTER(c_void_p))
_GetDVCInfo_t = CFUNCTYPE(c_int, c_void_p, c_uint, POINTER(NV_DISPLAY_DVC_INFO))
_SetDVCLevel_t = CFUNCTYPE(c_int, c_void_p, c_uint, c_int)
_GetDVCInfoEx_t = CFUNCTYPE(c_int, c_void_p, c_uint, POINTER(NV_DISPLAY_DVC_INFO_EX))
_SetDVCLevelEx_t = CFUNCTYPE(c_int, c_void_p, c_uint, POINTER(NV_DISPLAY_DVC_INFO_EX))


class VibranceController:
    def __init__(self):
        self.available = False
        self.full_range = False   # True when levels below 50% are supported (Ex API)
        self.active = False
        self._originals = {}      # device -> level saved before we changed it
        self._funcs = {}
        try:
            self._load()
            self.available = self._get_level(None) is not None
        except Exception as e:
            print(f"Digital Vibrance unavailable: {e}")
            self.available = False

    # --- NVAPI plumbing ---

    def _load(self):
        dll_name = "nvapi64.dll" if sizeof(c_void_p) == 8 else "nvapi.dll"
        dll = ctypes.CDLL(dll_name)
        query = dll.nvapi_QueryInterface
        query.restype = c_void_p
        query.argtypes = [c_uint]

        def get(fid, proto, required=True):
            ptr = query(fid)
            if not ptr:
                if required:
                    raise OSError(f"NVAPI function 0x{fid:08X} not found")
                return None
            return proto(ptr)

        init = get(_ID_INITIALIZE, _Initialize_t)
        if init() != NVAPI_OK:
            raise OSError("NvAPI_Initialize failed")

        self._funcs = {
            "enum": get(_ID_ENUM_NV_DISPLAY_HANDLE, _EnumNvidiaDisplayHandle_t),
            "assoc": get(_ID_GET_ASSOCIATED_NV_DISPLAY_HANDLE, _GetAssociatedNvidiaDisplayHandle_t),
            "get": get(_ID_GET_DVC_INFO, _GetDVCInfo_t, required=False),
            "set": get(_ID_SET_DVC_LEVEL, _SetDVCLevel_t, required=False),
            "get_ex": get(_ID_GET_DVC_INFO_EX, _GetDVCInfoEx_t, required=False),
            "set_ex": get(_ID_SET_DVC_LEVEL_EX, _SetDVCLevelEx_t, required=False),
        }
        self.full_range = bool(self._funcs["get_ex"] and self._funcs["set_ex"])
        if not self.full_range and not (self._funcs["get"] and self._funcs["set"]):
            raise OSError("No NVAPI DVC functions available")

    def _get_handle(self, device):
        """NVIDIA display handle of a GDI device ('\\\\.\\DISPLAY1'); None = primary,
        falling back to the first NVIDIA display. Returns None if not on the NVIDIA card."""
        handle = c_void_p()
        name = device or get_primary_display_name()
        if name:
            if self._funcs["assoc"](name.encode("ascii"), byref(handle)) == NVAPI_OK and handle.value:
                return handle
            if device:
                return None
        if self._funcs["enum"](0, byref(handle)) == NVAPI_OK and handle.value:
            return handle
        return None

    def _info_ex(self, handle):
        info = NV_DISPLAY_DVC_INFO_EX()
        info.version = _DVC_INFO_EX_VER
        if self._funcs["get_ex"](handle, 0, byref(info)) != NVAPI_OK:
            return None
        return info

    def _info_legacy(self, handle):
        info = NV_DISPLAY_DVC_INFO()
        info.version = _DVC_INFO_VER
        if self._funcs["get"](handle, 0, byref(info)) != NVAPI_OK:
            return None
        return info

    def _get_level(self, device):
        """Current level of a display in the API's own units, or None."""
        handle = self._get_handle(device)
        if not handle:
            return None
        info = self._info_ex(handle) if self.full_range else self._info_legacy(handle)
        return info.currentLevel if info else None

    def _set_level(self, device, level):
        handle = self._get_handle(device)
        if not handle:
            return False
        if self.full_range:
            info = self._info_ex(handle)
            if info is None:
                return False
            info.currentLevel = max(info.minLevel, min(info.maxLevel, int(level)))
            return self._funcs["set_ex"](handle, 0, byref(info)) == NVAPI_OK
        return self._funcs["set"](handle, 0, int(level)) == NVAPI_OK

    def _percent_to_level(self, device, percent):
        """Control Panel % -> API level for `device`, or None if it isn't an NVIDIA display."""
        percent = max(MIN_PERCENT, min(MAX_PERCENT, float(percent)))
        handle = self._get_handle(device)
        if not handle:
            return None
        if self.full_range:
            info = self._info_ex(handle)
            if info is None:
                return None
            # Ex levels normally are the percentage itself; map min/default/max to be safe
            if percent <= DEFAULT_PERCENT:
                t = percent / DEFAULT_PERCENT
                return round(info.minLevel + (info.defaultLevel - info.minLevel) * t)
            t = (percent - DEFAULT_PERCENT) / (MAX_PERCENT - DEFAULT_PERCENT)
            return round(info.defaultLevel + (info.maxLevel - info.defaultLevel) * t)
        info = self._info_legacy(handle)
        if info is None:
            return None
        frac = max(0.0, (percent - DEFAULT_PERCENT) / (MAX_PERCENT - DEFAULT_PERCENT))
        return max(info.minLevel, min(info.maxLevel, round(frac * info.maxLevel)))

    # --- Public API ---

    def supports(self, device):
        """True if `device` is driven by the NVIDIA card."""
        return self.available and self._get_handle(device) is not None

    def apply(self, percent, devices=None):
        """Set vibrance on `devices` (default: primary). Devices we changed before but
        that are not in the list get their original level back."""
        if not self.available:
            return False
        devices = list(devices) if devices else [None]
        self.restore([d for d in self._originals if d not in devices])
        ok_any = False
        for device in devices:
            try:
                level = self._percent_to_level(device, percent)
                if level is None:
                    continue  # not an NVIDIA display
                if device not in self._originals:
                    # Remember whatever the user had set (e.g. in NVIDIA Control Panel)
                    self._originals[device] = self._get_level(device)
                ok_any = self._set_level(device, level) or ok_any
            except Exception as e:
                print(f"Error applying vibrance on {device}: {e}")
        self.active = bool(self._originals)
        return ok_any

    def restore(self, devices=None):
        for device in list(devices if devices is not None else self._originals):
            original = self._originals.pop(device, None)
            if original is None:
                continue
            try:
                self._set_level(device, original)
            except Exception as e:
                print(f"Error restoring vibrance on {device}: {e}")
        self.active = bool(self._originals)
