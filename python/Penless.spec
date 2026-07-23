# -*- mode: python ; coding: utf-8 -*-
"""
Penless PyInstaller Spec File
==============================
Builds a single self-contained Penless.exe.

Replaces the C# publish.ps1 / dotnet publish --self-contained pipeline.

Key decisions:
  - onefile=True  → single .exe (no installer needed, just run it)
  - windowed=True → no black console window (same as WPF app)
  - icon           → reused from the original Desktop project
  - datas          → bundles server/static/ (the browser UI) and app.ico
  - hiddenimports  → modules that PyInstaller can't auto-detect through Flask
"""

import os

# ─── Paths ────────────────────────────────────────────────────────────────────
HERE = os.path.abspath('.')
STATIC_SRC  = os.path.join(HERE, 'server', 'static')
ICON_PATH   = os.path.join(HERE, '..', 'src', 'Penless.Desktop', 'app.ico')

# Use the icon if it exists, otherwise PyInstaller uses its default
icon = ICON_PATH if os.path.isfile(ICON_PATH) else None

# ─── Data files (bundled into the exe) ───────────────────────────────────────
# (source_path, dest_folder_inside_exe)
# server/static/  → accessible at runtime via sys._MEIPASS/server/static/
datas = [
    (STATIC_SRC, 'server/static'),
]

# Copy app.ico next to the exe AND into bundle root so tray + window icon work
if icon:
    datas.append((ICON_PATH, '.'))

# ─── Hidden imports ───────────────────────────────────────────────────────────
# Flask, Waitress, pystray, qrcode use dynamic imports that PyInstaller misses.
hidden_imports = [
    # Waitress internals
    'waitress',
    'waitress.server',
    'waitress.task',
    'waitress.channel',
    'waitress.utilities',
    # Flask internals
    'flask',
    'flask.templating',
    'flask_cors',
    # qrcode backends
    'qrcode',
    'qrcode.image.pil',
    'qrcode.image.base',
    # pystray backends (Windows uses win32)
    'pystray',
    'pystray._win32',
    # Pillow image formats used by QR + tray icon
    'PIL',
    'PIL.Image',
    'PIL.ImageDraw',
    'PIL.ImageTk',
    'PIL.PngImagePlugin',
    'PIL.BmpImagePlugin',
    # Tkinter
    'tkinter',
    'tkinter.filedialog',
    'tkinter.font',
    # Our own packages (needed when running from frozen exe)
    'config',
    'services',
    'services.file_service',
    'services.network_service',
    'services.transfer_logger',
    'server',
    'server.flask_app',
    'server.endpoints',
    'server.middleware',
    'desktop',
    'desktop.app',
    'desktop.tray',
]

# ─── Analysis ────────────────────────────────────────────────────────────────
a = Analysis(
    ['main.py'],
    pathex=[HERE],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Strip heavy unused packages to keep exe smaller
        'matplotlib', 'numpy', 'pandas', 'scipy', 'IPython',
        'jupyter', 'notebook', 'PyQt5', 'PyQt6', 'PySide6',
        'wx', 'gi', 'cv2', 'sklearn',
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Penless',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,           # compress with UPX if available (reduces size)
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,       # no black console window (replaces WPF Subsystem=Windows)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon,           # .ico file for the exe icon
    onefile=True,        # single self-contained .exe
)
