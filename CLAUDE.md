# NightVisionGoggles (fork di NightVisionFilterTool di zeroxpapone, GPL-3.0)

- App Windows in Python + **PySide6** (Qt), gira nella tray. Entry point: `launcher.py` -> `src/main.py`.
- Build: `python build.py` (PyInstaller, onefile, noconsole) -> `dist/NightVision.exe`.
  Il nome dell'app/exe è "NightVision" (`APP_NAME` in `src/utils.py`), il progetto si chiama NightVision Goggles.
- Filtro: gamma ramp GDI (`src/gamma.py`) + Digital Vibrance NVIDIA via NVAPI (`src/vibrance.py`).
  Multi-monitor: il filtro si applica ai monitor scelti; la vibrance solo su quelli collegati alla scheda NVIDIA.
  Su AMD/Intel funziona tutto tranne la vibrance.
- Hotkey globali con Win32 `RegisterHotKey` su thread dedicato (`src/input_manager.py`), NON la libreria `keyboard`
  (gli hook LL venivano rimossi da Windows dopo ore di idle).
- Le hotkey che non si registrano vengono mostrate in rosso nella GUI (`show_hotkey_status` in `src/gui.py`).
- Seconda istanza dell'exe = toggle del filtro via UDP su 127.0.0.1:65432 (`src/main.py`), usato da Stream Deck ecc.
- Config (`src/config.py`): portable in `config/` accanto all'exe (settings.json, presets.json);
  se la cartella non è scrivibile usa `%LOCALAPPDATA%\NightVision`. I file vecchi da `%LOCALAPPDATA%\NVFT`
  vengono importati al primo avvio. Scritture atomiche (file temp + replace).
- UI: finestra frameless con comportamento nativo Windows 11 (`src/frameless.py`), temi chiaro/scuro (`src/theme.py`),
  widget custom (`src/widgets.py`). Il preset "Default" esiste sempre e non si può rinominare/eliminare.
- Non ci sono test automatici: verificare lanciando `python launcher.py`.
- README, commit e testi della UI sono in inglese.
