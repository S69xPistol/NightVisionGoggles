import PyInstaller.__main__

PyInstaller.__main__.run([
    'launcher.py',
    '--name=NightVision',
    '--onefile',
    '--noconsole',
    '--icon=icon.ico',
    '--add-data=icon.png;.',
    '--add-data=icon.ico;.',
    # Only the Qt modules we use (keeps the exe small)
    '--exclude-module=PySide6.QtNetwork',
    '--exclude-module=PySide6.QtQml',
    '--exclude-module=PySide6.QtQuick',
    '--exclude-module=PySide6.QtSvg',
    '--exclude-module=PySide6.QtPdf',
    '--exclude-module=tkinter',
    '--clean',
])
