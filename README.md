# NightVision Goggle

A Windows tray app that brightens dark scenes in games (made with Escape from Tarkov's nights in mind) by changing the monitor's gamma ramp, with optional NVIDIA Digital Vibrance.

Based on [NightVisionFilterTool](https://github.com/zeroxpapone/NightVisionFilterTool) by **zeroxpapone**, released under GPL-3.0. This version adds a redesigned interface, Digital Vibrance, multi-monitor support and presets management.

## Features

* **Luminance**: brightness, contrast and gamma, applied through the Windows gamma ramp (works with NVIDIA, AMD and Intel GPUs).
* **Color channels**: per-channel red / green / blue multiplier.
* **Digital Vibrance (NVIDIA only)**: 0–100%, same scale as the NVIDIA Control Panel (50% is the driver default). Restored to its previous value when the filter is turned off.
* **Monitors**: apply the filter to one or more screens. Vibrance works on the monitors connected to the NVIDIA card.
* **Presets** in the right sidebar: **New** and **Duplicate** create a preset right away; slider changes stay "unsaved" until you press **Save** (or **Discard**). The **Default** preset (neutral values) is always first and can't be renamed or deleted.
* **Hotkeys**: one to toggle the filter (**Ctrl + F10** by default) and one per preset. They use the native Windows `RegisterHotKey` API, so they keep working after long idle periods. The registered combination is not forwarded to the game. Press Esc while recording to cancel.
* **Live preview** of the current values, dark and light theme, launch with Windows, start minimized, always on top, close to tray (gear icon).
* Native Windows 11 window behaviour: Snap, Snap Layouts, resizing and animations.

Check that the values suit your monitor before relying on them in a match: hop on an offline raid to try them out.

## Install / run

* **Download**: check the Releases page for the latest `NightVision.exe` (if available).
* **From source** (Python 3.12):
  ```
  python -m venv .venv
  .venv\Scripts\pip install -r requirements.txt
  .venv\Scripts\python launcher.py
  ```
* **Build the exe**: `.venv\Scripts\python build.py` → `dist\NightVision.exe`.
* **Regenerate the icon**: `.venv\Scripts\python tools\make_icon.py`.

Settings and presets are stored in a `config` folder next to the executable (`settings.json`, `presets.json`), so the app is portable. If that folder is not writable (e.g. inside Program Files) they go to `%LOCALAPPDATA%\NightVision`. Settings from NVFT 2.x are imported on first start.

## Stream Deck / MacroButtons

Running the exe while NightVision is already open toggles the filter, the same way the hotkey does. So a Stream Deck button can simply run `NightVision.exe`, and in VoiceMeeter MacroButtons you can use `System.Execute("PATH TO NightVision.exe","","");`.

## License

Distributed under the **GNU General Public License v3.0**, like the original project. See `LICENSE` for more information.

**Disclaimer:** This software is provided **"as is"**, without warranty of any kind, express or implied. The authors are not responsible for any hardware damage, data loss, or **game account bans** resulting from the use of this tool. Use it at your own risk.
