"""
Penless — main entry point.

Boots up the Tkinter window, wires up the system tray icon,
and kicks off the main event loop.

Usage:
    python main.py
"""

import os
import sys
import tkinter as tk


def _find_icon():
    """Try to locate app.ico in a few likely spots."""
    candidates = []

    # PyInstaller bundles everything into a temp dir
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        candidates.append(os.path.join(sys._MEIPASS, 'app.ico'))

    # next to this script
    here = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(here, 'app.ico'))

    # the .NET project might still have one lying around
    candidates.append(os.path.join(here, '..', 'src', 'Penless.Desktop', 'app.ico'))

    for path in candidates:
        if os.path.isfile(path):
            return os.path.abspath(path)
    return None


def main():
    # make sure our own package is importable
    root_dir = os.path.dirname(os.path.abspath(__file__))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

    # same deal for PyInstaller's temp extraction folder
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        meipass = sys._MEIPASS
        if meipass not in sys.path:
            sys.path.insert(0, meipass)

    from desktop.app import MainWindow
    from desktop.tray import SystemTray

    icon_path = _find_icon()

    root = tk.Tk()
    root.withdraw()  # don't show until everything's ready

    _exit_called = False

    def on_exit():
        """Shut down tray + window cleanly."""
        nonlocal _exit_called
        if _exit_called:
            return
        _exit_called = True
        tray.stop()
        try:
            root.quit()
            root.destroy()
        except Exception:
            pass

    window = MainWindow(root, icon_path=icon_path, on_exit_requested=on_exit)

    # tray callbacks need to hop onto the Tk thread
    def on_tray_open():
        root.after(0, window.show)

    def on_tray_exit():
        root.after(0, window.request_close)

    tray = SystemTray(
        icon_path=icon_path,
        on_open=on_tray_open,
        on_exit=on_tray_exit,
    )
    tray.start()

    root.deiconify()

    try:
        root.mainloop()
    finally:
        tray.stop()


if __name__ == "__main__":
    main()
