import sys
import socket
import threading

from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu

from .utils import SingleInstance, resource_path, set_app_user_model_id, APP_NAME
from .config import ConfigManager
from .gamma import GammaController
from .vibrance import VibranceController
from .input_manager import InputManager
from . import theme
from .gui import SettingsApp

LOCAL_PORT = 65432


def try_send_toggle():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(0.1)
        sock.sendto(b"TOGGLE", ("127.0.0.1", LOCAL_PORT))
        sock.close()
    except Exception:
        pass


def start_ipc_listener(window):
    """A second launch of the exe (Stream Deck, MacroButtons...) toggles the filter."""
    def server():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind(("127.0.0.1", LOCAL_PORT))
            while True:
                data, _ = sock.recvfrom(1024)
                if data == b"TOGGLE":
                    window.external_toggle()
        except OSError:
            print(f"IPC Port {LOCAL_PORT} busy. Remote toggle disabled.")
        except Exception as e:
            print(f"IPC Error: {e}")

    threading.Thread(target=server, daemon=True).start()


def main():
    # 1. Single Instance Check
    instance = SingleInstance()
    if instance.check():
        # Already running? Send toggle command then exit
        try_send_toggle()
        sys.exit(0)

    set_app_user_model_id()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)  # closing the window hides it to the tray
    app.setWindowIcon(QIcon(resource_path("icon.ico")))
    theme.init_fonts()

    # 2. Initialize Components
    config = ConfigManager()
    gamma = GammaController()
    vibrance = VibranceController()

    def quit_app():
        config.save_settings()
        gamma.restore()
        vibrance.restore()
        app.quit()

    # 3. GUI
    window = SettingsApp(config, gamma, vibrance, None, on_quit=quit_app)

    # 4. Global hotkeys
    input_mgr = InputManager(
        config,
        toggle_callback=window.external_toggle,
        preset_callback=window.external_load_preset
    )
    window.input_manager = input_mgr
    input_mgr.set_status_callback(window.external_hotkey_status)

    # 5. Remote toggle from a second launch
    start_ipc_listener(window)

    # 6. Tray icon
    tray = QSystemTrayIcon(QIcon(resource_path("icon.ico")), app)
    tray.setToolTip(APP_NAME)
    menu = QMenu()
    for text, slot in ((f"Open {APP_NAME}", window.show_window), ("Toggle filter", window.toggle_filter),
                       (None, None), ("Exit", quit_app)):
        if text is None:
            menu.addSeparator()
            continue
        action = QAction(text, menu)
        action.triggered.connect(slot)
        menu.addAction(action)
    tray.setContextMenu(menu)
    tray.activated.connect(lambda reason: window.show_window()
                           if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick) else None)
    tray.show()

    # 7. Run App
    if not config.current_settings.get("start_minimized", True):
        window.show_window()

    try:
        app.exec()
    finally:
        gamma.restore()
        vibrance.restore()
        instance.release()


if __name__ == "__main__":
    main()
