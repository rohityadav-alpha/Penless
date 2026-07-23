"""
System tray icon using pystray.

Shows "Open Penless" (bold/default) and "Exit" in the right-click menu.
Runs in its own daemon thread so it doesn't block the Tk mainloop.
"""

import threading
from typing import Callable, Optional

try:
    import pystray
    from PIL import Image, ImageDraw
    _PYSTRAY_AVAILABLE = True
except ImportError:
    _PYSTRAY_AVAILABLE = False


def _make_fallback_icon():
    """Quick 64x64 navy square with a white antenna shape, in case app.ico is missing."""
    img = Image.new("RGB", (64, 64), color=(0, 0, 128))
    draw = ImageDraw.Draw(img)
    draw.rectangle([28, 20, 36, 50], fill=(255, 255, 255))
    draw.ellipse([20, 12, 44, 24], fill=(255, 255, 255))
    return img


class SystemTray:
    """Manages the system tray icon and its context menu."""

    def __init__(self, icon_path: Optional[str], on_open: Callable, on_exit: Callable):
        self._on_open = on_open
        self._on_exit = on_exit
        self._tray = None
        self._icon_path = icon_path

    def start(self):
        """Spin up the tray icon in a background thread."""
        if not _PYSTRAY_AVAILABLE:
            return

        try:
            icon_img = Image.open(self._icon_path) if self._icon_path else None
            if icon_img is None:
                raise ValueError("no path")
        except Exception:
            icon_img = _make_fallback_icon()

        menu = pystray.Menu(
            pystray.MenuItem("Open Penless", self._handle_open, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", self._handle_exit),
        )

        self._tray = pystray.Icon(
            name="Penless",
            icon=icon_img,
            title="Penless — Local File Transfer",
            menu=menu,
        )

        t = threading.Thread(target=self._tray.run, daemon=True, name="penless-tray")
        t.start()

    def stop(self):
        """Kill the tray icon."""
        if self._tray is not None:
            try:
                self._tray.stop()
            except Exception:
                pass
            self._tray = None

    def _handle_open(self, icon, item):
        self._on_open()

    def _handle_exit(self, icon, item):
        self._on_exit()
