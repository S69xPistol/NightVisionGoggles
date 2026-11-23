import ctypes
import math
from ctypes import windll, byref, Structure, c_ushort, POINTER

from .utils import get_primary_display_name

# Windows GDI Structures
class RAMP(Structure):
    _fields_ = [("Red", c_ushort * 256), ("Green", c_ushort * 256), ("Blue", c_ushort * 256)]

windll.gdi32.CreateDCW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_void_p]
windll.gdi32.CreateDCW.restype = ctypes.c_void_p
windll.gdi32.DeleteDC.argtypes = [ctypes.c_void_p]
windll.gdi32.SetDeviceGammaRamp.argtypes = [ctypes.c_void_p, POINTER(RAMP)]
windll.gdi32.GetDeviceGammaRamp.argtypes = [ctypes.c_void_p, POINTER(RAMP)]


def compute_curves(settings):
    """Normalized (0..1) output for each of the 256 input levels, per channel.
    Shared by the real gamma ramp and the GUI preview so they always match.
    keys: brightness, contrast, gamma, red_scale, green_scale, blue_scale"""
    b_input = float(settings.get("brightness", 0.53))
    c_input = float(settings.get("contrast", 0.85))
    gamma_val = max(0.1, float(settings.get("gamma", 2.4)))
    scales = (float(settings.get("red_scale", 1.0)),
              float(settings.get("green_scale", 1.0)),
              float(settings.get("blue_scale", 1.0)))

    brightness_offset = b_input - 0.5
    contrast_gain = c_input * 2.0

    base = []
    for i in range(256):
        val = math.pow(i / 255.0, 1.0 / gamma_val)
        val = val + brightness_offset
        val = (val - 0.5) * contrast_gain + 0.5
        base.append(max(0.0, min(1.0, val)))
    return tuple([min(1.0, v * s) for v in base] for s in scales)


class GammaController:
    """Applies the filter as a gamma ramp on one or more monitors.
    Each monitor's original ramp is saved the first time it is changed and
    put back by restore() (or when the monitor is deselected)."""

    def __init__(self):
        self.active = False
        self._originals = {}  # device name -> RAMP saved before we touched it

    @staticmethod
    def _dc(device):
        if device:
            return windll.gdi32.CreateDCW(None, device, None, None)
        return windll.gdi32.CreateDCW("DISPLAY", None, None, None)

    @staticmethod
    def _linear_ramp():
        ramp = RAMP()
        for i in range(256):
            ramp.Red[i] = ramp.Green[i] = ramp.Blue[i] = int((i / 255.0) * 65535)
        return ramp

    def _set_ramp(self, device, ramp):
        dc = self._dc(device)
        if not dc:
            return False
        try:
            return bool(windll.gdi32.SetDeviceGammaRamp(dc, byref(ramp)))
        finally:
            windll.gdi32.DeleteDC(dc)

    def _save_original(self, device):
        if device in self._originals:
            return
        ramp = RAMP()
        dc = self._dc(device)
        ok = False
        if dc:
            ok = windll.gdi32.GetDeviceGammaRamp(dc, byref(ramp))
            windll.gdi32.DeleteDC(dc)
        self._originals[device] = ramp if ok else self._linear_ramp()

    def restore(self, devices=None):
        """Put back the original ramp on the given monitors (default: all we changed)."""
        for device in list(devices if devices is not None else self._originals):
            original = self._originals.pop(device, None)
            if original is not None:
                self._set_ramp(device, original)
        if not self._originals:
            self.active = False

    def apply_settings(self, settings, devices=None):
        """Apply the filter to `devices` (GDI names like '\\\\.\\DISPLAY1'; default: primary).
        Monitors that were filtered before but are no longer in `devices` are restored."""
        devices = list(devices) if devices else [get_primary_display_name()]
        try:
            red, green, blue = compute_curves(settings)
            new_ramp = RAMP()
            for i in range(256):
                new_ramp.Red[i] = int(red[i] * 65535)
                new_ramp.Green[i] = int(green[i] * 65535)
                new_ramp.Blue[i] = int(blue[i] * 65535)
        except Exception as e:
            print(f"Error computing gamma: {e}")
            return False

        self.restore([d for d in self._originals if d not in devices])

        ok_any = False
        for device in devices:
            self._save_original(device)
            if self._set_ramp(device, new_ramp):
                ok_any = True
            else:
                print(f"SetDeviceGammaRamp failed on {device}")
        self.active = ok_any
        return ok_any
