"""
Settings and presets, stored next to the executable (portable):

    NightVision.exe
    config/
        settings.json   app options, toggle hotkey, monitors, window geometry, last preset
        presets.json    every preset (values + hotkey); "Default" always exists

If the exe folder is not writable (e.g. Program Files) the files go to
%LOCALAPPDATA%\\NightVision instead. Files from older versions
(%LOCALAPPDATA%\\NVFT or next to the exe) are imported on first start.
Every write goes to a temp file first and then replaces the old one, so a crash
or power loss mid-save can't leave a half-written file.
"""
import json
import os
import sys
import winreg
from .utils import get_app_dir, APP_NAME

APP_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_RUN_NAME = APP_NAME
LEGACY_RUN_NAMES = ["NVFT"]

DEFAULT_PRESET = "Default"
NEW_PRESET_BASE = "New Preset"

# Filter values a preset is made of
VALUE_KEYS = ["brightness", "contrast", "gamma", "red_scale", "green_scale", "blue_scale", "vibrance"]
# Neutral values: with these the gamma ramp is unchanged (the "Default" preset)
DEFAULT_VALUES = {
    "brightness": 0.5,
    "contrast": 0.5,
    "gamma": 1.0,
    "red_scale": 1.0,
    "green_scale": 1.0,
    "blue_scale": 1.0,
    "vibrance": 50,
}
DEFAULT_SETTINGS = {
    "hotkey": "ctrl+f10",
    "autostart": False,
    "start_minimized": True,
    "always_on_top": False,
    "close_to_tray": True,
    "dark_mode": True,
    "monitors": [],          # GDI device names; empty = primary monitor only
    "active_preset": DEFAULT_PRESET,
    "window_geometry": None,  # Qt saveGeometry() as hex
}


def _atomic_write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    os.replace(tmp, path)


def _read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"Error reading {path}: {e}")
        return None


def _writable_dir(path):
    try:
        os.makedirs(path, exist_ok=True)
        probe = os.path.join(path, ".write_test")
        with open(probe, "w") as f:
            f.write("ok")
        os.remove(probe)
        return True
    except OSError:
        return False


class ConfigManager:
    def __init__(self):
        portable_dir = os.path.join(get_app_dir(), "config")
        if _writable_dir(portable_dir):
            self.app_dir = portable_dir
            self.portable = True
        else:
            self.app_dir = os.path.join(os.environ["LOCALAPPDATA"], APP_NAME)
            os.makedirs(self.app_dir, exist_ok=True)
            self.portable = False

        self.config_file = os.path.join(self.app_dir, "settings.json")
        self.presets_file = os.path.join(self.app_dir, "presets.json")

        self.default_settings = dict(DEFAULT_SETTINGS)
        self.current_settings = dict(DEFAULT_SETTINGS)
        self.presets = {}

        legacy = None
        if not os.path.exists(self.config_file) and not os.path.exists(self.presets_file):
            legacy = self._find_legacy_files()

        self.load_settings(legacy)
        self.load_presets(legacy)

        # Sync autostart status with registry
        self.sync_autostart_registry()

    # --- Loading / migration ---

    def _find_legacy_files(self):
        """settings/presets of NVFT 2.x: %LOCALAPPDATA%\\NVFT, or the old exe folder."""
        candidates = [os.path.join(os.environ.get("LOCALAPPDATA", ""), "NVFT"), get_app_dir()]
        for folder in candidates:
            s = _read_json(os.path.join(folder, "settings.json"))
            p = _read_json(os.path.join(folder, "presets.json"))
            if s is not None or p is not None:
                print(f"Importing settings from {folder}")
                return {"settings": s or {}, "presets": p or {}}
        return None

    def load_settings(self, legacy=None):
        data = legacy["settings"] if legacy else _read_json(self.config_file)
        if isinstance(data, dict):
            for key in DEFAULT_SETTINGS:
                if key in data:
                    self.current_settings[key] = data[key]
        if legacy or data is None:
            self.save_settings()

    def load_presets(self, legacy=None):
        if legacy:
            raw = legacy["presets"]
            old_values = {k: legacy["settings"][k] for k in VALUE_KEYS if k in legacy["settings"]}
        else:
            raw = _read_json(self.presets_file)
            old_values = {}
        if isinstance(raw, dict) and isinstance(raw.get("presets"), dict):
            raw = raw["presets"]  # current format: {"version": 2, "presets": {...}}

        self.presets = {}
        if isinstance(raw, dict):
            for name, data in raw.items():
                if isinstance(data, dict) and str(name).strip():
                    self.presets[str(name).strip()] = self._clean_preset(data)

        if DEFAULT_PRESET not in self.presets:
            self.presets[DEFAULT_PRESET] = self._clean_preset(DEFAULT_VALUES)
            # Old versions kept the working values in settings.json: keep them as a preset
            if old_values and any(abs(float(v) - DEFAULT_VALUES[k]) > 1e-6 for k, v in old_values.items()):
                values = dict(DEFAULT_VALUES)
                values.update(old_values)
                self.presets[self.free_name("NVFT settings", numbered=False)] = self._clean_preset(values)
        if self.current_settings.get("active_preset") not in self.presets:
            self.current_settings["active_preset"] = DEFAULT_PRESET
        if legacy or raw is None:
            self.save_presets()

    @staticmethod
    def _clean_preset(data):
        preset = {}
        for key in VALUE_KEYS:
            try:
                preset[key] = round(float(data.get(key, DEFAULT_VALUES[key])), 4)  # drop float noise
            except (TypeError, ValueError):
                preset[key] = DEFAULT_VALUES[key]
        preset["hotkey"] = data.get("hotkey") or None
        return preset

    # --- Saving ---

    def save_settings(self):
        try:
            _atomic_write_json(self.config_file, self.current_settings)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def save_presets(self):
        try:
            _atomic_write_json(self.presets_file, {"version": 2, "presets": self.presets})
        except Exception as e:
            print(f"Error saving presets: {e}")

    def update_setting(self, key, value, save=True):
        self.current_settings[key] = value
        if save:
            self.save_settings()

    # --- Presets ---

    def get_preset_names(self):
        """'Default' first, then every other preset in alphabetical order (case-insensitive)."""
        others = sorted((n for n in self.presets if n != DEFAULT_PRESET), key=str.casefold)
        return [DEFAULT_PRESET] + others

    def preset_values(self, name):
        preset = self.presets.get(name) or self.presets[DEFAULT_PRESET]
        return {k: preset[k] for k in VALUE_KEYS}

    def name_taken(self, name, exclude=None):
        """Is `name` used by a preset other than `exclude`? Case-insensitive, trimmed."""
        key = name.strip().casefold()
        return any(n.casefold() == key for n in self.presets if n != exclude)

    def free_name(self, base, numbered):
        """First unused name: numbered -> 'base 1', 'base 2', ...; else 'base', 'base 2', ..."""
        if not numbered and not self.name_taken(base):
            return base
        n = 1 if numbered else 2
        while self.name_taken(f"{base} {n}"):
            n += 1
        return f"{base} {n}"

    def create_preset(self, name, values):
        """Add a preset (saved immediately). Returns its name."""
        preset = self._clean_preset(values)
        preset["hotkey"] = None
        self.presets[name] = preset
        self.save_presets()
        return name

    def update_preset(self, name, values, new_name=None):
        """Save new values (and optionally a new name) for an existing preset.
        Returns the final name, or None if the new name is invalid/taken."""
        if name not in self.presets:
            return None
        if new_name is not None:
            new_name = new_name.strip()
            if name == DEFAULT_PRESET or not new_name:
                new_name = name
            elif new_name != name and self.name_taken(new_name, exclude=name):
                return None
        else:
            new_name = name
        preset = self._clean_preset(values)
        preset["hotkey"] = self.presets[name].get("hotkey")
        if new_name != name:
            del self.presets[name]
            if self.current_settings.get("active_preset") == name:
                self.current_settings["active_preset"] = new_name
                self.save_settings()
        self.presets[new_name] = preset
        self.save_presets()
        return new_name

    def delete_preset(self, name):
        if name == DEFAULT_PRESET or name not in self.presets:
            return False
        del self.presets[name]
        if self.current_settings.get("active_preset") == name:
            self.current_settings["active_preset"] = DEFAULT_PRESET
            self.save_settings()
        self.save_presets()
        return True

    # --- Autostart / Registry Logic ---

    def sync_autostart_registry(self):
        self.set_autostart(self.current_settings.get("autostart", False))

    def set_autostart(self, enabled: bool):
        if getattr(sys, 'frozen', False):
            cmd = f'"{sys.executable}"'
        else:
            # Running from source: launcher.py puts the project root on sys.path
            pythonw = sys.executable.replace("python.exe", "pythonw.exe")
            cmd = f'"{pythonw}" "{os.path.join(get_app_dir(), "launcher.py")}"'

        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, APP_RUN_KEY, 0, winreg.KEY_ALL_ACCESS)
        except FileNotFoundError:
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, APP_RUN_KEY)

        try:
            if enabled:
                # NightVision replaces NVFT: don't start both at sign-in
                for legacy in LEGACY_RUN_NAMES:
                    try:
                        winreg.DeleteValue(key, legacy)
                    except FileNotFoundError:
                        pass
                winreg.SetValueEx(key, APP_RUN_NAME, 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(key, APP_RUN_NAME)
                except FileNotFoundError:
                    pass
        finally:
            winreg.CloseKey(key)
