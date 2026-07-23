"""
Penless desktop window — the main GUI built with Tkinter.

Win98-inspired retro look with navy title bar, raised 3D buttons,
sunken text fields, and a Courier monospace activity log. Has sections
for server status, QR code, configuration, and live logs.
"""

import io
import os
import sys
import threading
import tkinter as tk
import webbrowser
from tkinter import filedialog, font as tkfont
from typing import Optional, Callable

try:
    from PIL import Image as PilImage, ImageTk
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

# -- Win98 color palette --

C_GRAY       = "#C0C0C0"
C_DARK_GRAY  = "#808080"
C_DARKER     = "#404040"
C_WHITE      = "#FFFFFF"
C_BLACK      = "#000000"
C_NAVY       = "#000080"
C_TITLE_END  = "#1084D0"
C_GREEN      = "#008000"
C_RED        = "#800000"
C_SILVER     = "#D4D0C8"

FONT_SYSTEM  = ("Tahoma", 9)
FONT_BOLD    = ("Tahoma", 9, "bold")
FONT_MONO    = ("Courier New", 8)
FONT_SMALL   = ("Tahoma", 8)


def _raised_border(widget, **kwargs):
    widget.config(relief=tk.RAISED, bd=2, **kwargs)


def _sunken_border(widget, **kwargs):
    widget.config(relief=tk.SUNKEN, bd=2, **kwargs)


class Win98Button(tk.Button):
    """Chunky raised button with hover highlight, like the real thing."""

    def __init__(self, master, danger=False, **kwargs):
        defaults = dict(
            bg=C_GRAY, fg=C_RED if danger else C_BLACK,
            relief=tk.RAISED, bd=2,
            font=FONT_SYSTEM,
            cursor="arrow",
            activebackground=C_SILVER,
            activeforeground=C_RED if danger else C_BLACK,
            padx=12, pady=3,
        )
        defaults.update(kwargs)
        super().__init__(master, **defaults)
        self.bind("<Enter>", lambda e: self.config(bg=C_SILVER))
        self.bind("<Leave>", lambda e: self.config(bg=C_GRAY))


class Win98Entry(tk.Entry):
    """Sunken white text input."""

    def __init__(self, master, **kwargs):
        defaults = dict(
            bg=C_WHITE, fg=C_BLACK,
            relief=tk.SUNKEN, bd=2,
            font=FONT_SYSTEM,
            insertbackground=C_BLACK,
        )
        defaults.update(kwargs)
        super().__init__(master, **defaults)


class SectionFrame(tk.LabelFrame):
    """Grooved group box for each UI section."""

    def __init__(self, master, title="", **kwargs):
        super().__init__(
            master, text=title, font=FONT_BOLD,
            fg=C_BLACK, bg=C_GRAY,
            relief=tk.GROOVE, bd=2,
            padx=8, pady=6, **kwargs,
        )


# ---------------------------------------------------------------------------

class MainWindow:
    """
    The main application window. Gets a Tk root from main.py rather than
    subclassing Tk directly — keeps the startup logic separate.
    """

    def __init__(self, root: tk.Tk, icon_path: Optional[str] = None,
                 on_exit_requested: Optional[Callable] = None):
        self.root = root
        self._icon_path = icon_path
        self._on_exit_requested = on_exit_requested

        self._flask_server = None
        self._has_shown_tray_hint = False
        self._is_closing_for_real = False

        self._setup_window()
        self._build_ui()
        self._on_load()

    # -- window chrome --

    def _setup_window(self):
        self.root.title("Penless — Local File Transfer")
        self.root.geometry("600x760")
        self.root.minsize(480, 580)
        self.root.configure(bg=C_GRAY)
        self.root.resizable(True, True)

        if self._icon_path and os.path.isfile(self._icon_path):
            try:
                self.root.iconbitmap(self._icon_path)
            except Exception:
                pass

        # center it
        self.root.update_idletasks()
        w, h = 600, 760
        x = (self.root.winfo_screenwidth()  - w) // 2
        y = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

        # clicking X hides to tray instead of closing
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # -- build the whole UI --

    def _build_ui(self):
        # navy title bar across the top
        title_frame = tk.Frame(self.root, bg=C_NAVY, height=26)
        title_frame.pack(fill=tk.X, side=tk.TOP)
        title_frame.pack_propagate(False)

        tk.Label(
            title_frame, text="📡  Penless — Local File Transfer",
            bg=C_NAVY, fg=C_WHITE, font=FONT_BOLD,
            anchor="w", padx=8,
        ).pack(side=tk.LEFT, fill=tk.Y)

        # decorative caption buttons (?, ✕)
        for ch in ("?", "✕"):
            tk.Label(
                title_frame, text=ch, bg=C_GRAY, fg=C_BLACK,
                font=("Tahoma", 8, "bold"), width=2,
                relief=tk.RAISED, bd=1,
            ).pack(side=tk.RIGHT, padx=1, pady=4)

        # scrollable content area
        canvas = tk.Canvas(self.root, bg=C_GRAY, highlightthickness=0)
        scrollbar = tk.Scrollbar(self.root, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._content = tk.Frame(canvas, bg=C_GRAY, padx=8, pady=8)
        _canvas_window = canvas.create_window((0, 0), window=self._content, anchor="nw")

        def _on_frame_configure(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
        def _on_canvas_configure(e):
            canvas.itemconfig(_canvas_window, width=e.width)
        self._content.bind("<Configure>", _on_frame_configure)
        canvas.bind("<Configure>", _on_canvas_configure)

        # mousewheel
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))

        # ---- server status section ----
        status_frame = SectionFrame(self._content, title="Server Status")
        status_frame.pack(fill=tk.X, pady=(0, 8))

        dot_row = tk.Frame(status_frame, bg=C_GRAY)
        dot_row.pack(anchor="w", pady=(0, 6))

        self._status_dot = tk.Canvas(dot_row, width=12, height=12, bg=C_GRAY, highlightthickness=0)
        self._status_dot.pack(side=tk.LEFT, padx=(0, 6))
        self._dot_oval = self._status_dot.create_oval(1, 1, 11, 11, fill=C_RED, outline=C_DARKER)

        self._status_text = tk.Label(dot_row, text="Stopped", font=FONT_BOLD, bg=C_GRAY, fg=C_BLACK)
        self._status_text.pack(side=tk.LEFT)

        tk.Label(status_frame, text="Local URL:", font=FONT_SYSTEM, bg=C_GRAY, anchor="w").pack(anchor="w")
        self._url_label = tk.Label(
            status_frame, text="—", font=FONT_BOLD, fg=C_NAVY, bg=C_GRAY,
            cursor="hand2", anchor="w",
        )
        self._url_label.pack(anchor="w", pady=(0, 4))
        self._url_label.bind("<Button-1>", self._on_url_click)

        tk.Label(status_frame, text="Local IP:", font=FONT_SYSTEM, bg=C_GRAY, anchor="w").pack(anchor="w")
        self._ip_label = tk.Label(status_frame, text="—", font=FONT_BOLD, fg=C_NAVY, bg=C_GRAY, anchor="w")
        self._ip_label.pack(anchor="w", pady=(0, 6))

        btn_row = tk.Frame(status_frame, bg=C_GRAY)
        btn_row.pack(anchor="w")

        self._start_btn = Win98Button(btn_row, text="▶  Start Server", command=self._on_start)
        self._start_btn.pack(side=tk.LEFT, padx=(0, 6))

        self._stop_btn = Win98Button(btn_row, text="■  Stop Server", danger=True,
                                     command=self._on_stop, state=tk.DISABLED)
        self._stop_btn.pack(side=tk.LEFT)

        # ---- QR code section (hidden until server starts) ----
        self._qr_frame = SectionFrame(self._content, title="Scan to Connect (QR Code)")

        self._qr_image_label = tk.Label(self._qr_frame, bg=C_WHITE, relief=tk.SUNKEN, bd=2)
        self._qr_image_label.pack(pady=4)

        self._qr_url_label = tk.Label(self._qr_frame, text="", font=FONT_SMALL, fg=C_NAVY, bg=C_GRAY)
        self._qr_url_label.pack()

        # ---- configuration section ----
        config_frame = SectionFrame(self._content, title="Configuration")
        config_frame.pack(fill=tk.X, pady=(0, 8))

        tk.Label(config_frame, text="Shared Folder:", font=FONT_SYSTEM, bg=C_GRAY, anchor="w").pack(anchor="w")
        folder_row = tk.Frame(config_frame, bg=C_GRAY)
        folder_row.pack(fill=tk.X, pady=(0, 6))

        self._folder_var = tk.StringVar(value="SharedFiles")
        self._folder_entry = Win98Entry(folder_row, textvariable=self._folder_var)
        self._folder_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        Win98Button(folder_row, text="Browse...", command=self._on_browse, padx=8).pack(side=tk.LEFT, padx=(6, 0))

        tk.Label(config_frame, text="Port:", font=FONT_SYSTEM, bg=C_GRAY, anchor="w").pack(anchor="w")
        self._port_var = tk.StringVar(value="8080")
        self._port_entry = Win98Entry(config_frame, textvariable=self._port_var, width=10)
        self._port_entry.pack(anchor="w", pady=(0, 6))

        tk.Label(config_frame, text="PIN (leave empty for open access):",
                 font=FONT_SYSTEM, bg=C_GRAY, anchor="w").pack(anchor="w")
        self._pin_var = tk.StringVar()
        self._pin_entry = Win98Entry(config_frame, textvariable=self._pin_var, show="*", width=15)
        self._pin_entry.pack(anchor="w")

        # ---- activity log section ----
        log_frame = SectionFrame(self._content, title="Activity Log")
        log_frame.pack(fill=tk.X, pady=(0, 8))

        log_header = tk.Frame(log_frame, bg=C_GRAY)
        log_header.pack(fill=tk.X, pady=(0, 4))

        tk.Label(log_header, text="", bg=C_GRAY).pack(side=tk.LEFT, fill=tk.X, expand=True)
        Win98Button(log_header, text="Clear", padx=8, command=self._on_clear_log).pack(side=tk.RIGHT)

        log_container = tk.Frame(log_frame, bg=C_WHITE, relief=tk.SUNKEN, bd=2)
        log_container.pack(fill=tk.X)

        self._log_scroll = tk.Scrollbar(log_container)
        self._log_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self._log_text = tk.Text(
            log_container, height=8,
            font=FONT_MONO, bg=C_WHITE, fg=C_BLACK,
            state=tk.DISABLED, wrap=tk.WORD,
            yscrollcommand=self._log_scroll.set,
            relief=tk.FLAT, bd=0,
        )
        self._log_text.pack(fill=tk.X)
        self._log_scroll.config(command=self._log_text.yview)

        # ---- status bar at the bottom ----
        status_bar = tk.Frame(self.root, bg=C_GRAY, relief=tk.SUNKEN, bd=1)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        self._status_bar_text = tk.Label(
            status_bar, text="Ready", font=FONT_SMALL,
            bg=C_GRAY, fg=C_BLACK, anchor="w", padx=6, pady=2,
        )
        self._status_bar_text.pack(side=tk.LEFT)

    # -- initial setup on load --

    def _on_load(self):
        from services.network_service import NetworkService
        self._net = NetworkService()

        # figure out where SharedFiles should live
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

        default_folder = os.path.join(base_dir, "SharedFiles")
        self._folder_var.set(default_folder)
        os.makedirs(default_folder, exist_ok=True)

        ip = self._net.get_local_ip_address()
        self._ip_label.config(text=ip)
        self._append_log(f"Local IP detected: {ip}")

        if not self._net.is_network_available():
            self._append_log("⚠ No network connection detected. Other devices won't be able to connect.")

    # -- start / stop --

    def _on_start(self):
        if self._flask_server and self._flask_server.is_running:
            self._append_log("Server is already running.")
            return

        port = 8080
        try:
            p = int(self._port_var.get().strip())
            if 1 <= p <= 65535:
                port = p
            else:
                raise ValueError
        except ValueError:
            self._append_log("⚠ Invalid port. Using default 8080.")
            self._port_var.set("8080")

        shared_folder = self._folder_var.get().strip()
        if not shared_folder:
            base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            shared_folder = os.path.join(base_dir, "SharedFiles")
            self._folder_var.set(shared_folder)

        pin = self._pin_var.get().strip()

        from config import PenlessSettings
        from server.flask_app import FlaskServer

        settings = PenlessSettings(
            shared_folder=shared_folder,
            port=port,
            pin=pin,
            max_upload_size_bytes=2 * 1024 * 1024 * 1024,
        )

        self._set_config_enabled(False)
        self._append_log(f"Starting server on port {port}...")

        def _start_thread():
            try:
                server = FlaskServer(settings)
                server.transfer_logger.add_listener(self._on_log_entry)
                server.start()

                ip = self._net.get_local_ip_address()
                url = f"http://{ip}:{port}"

                # update the UI on the main thread
                self.root.after(0, lambda: self._on_server_started(server, ip, url, port, pin))
            except Exception as exc:
                self.root.after(0, lambda: self._on_server_start_failed(str(exc)))

        threading.Thread(target=_start_thread, daemon=True, name="start-server-thread").start()

    def _on_server_started(self, server, ip, url, port, pin):
        self._flask_server = server

        self._status_dot.itemconfig(self._dot_oval, fill=C_GREEN)
        self._status_text.config(text="Running")
        self._url_label.config(text=url)
        self._ip_label.config(text=ip)
        self._status_bar_text.config(text=f"Server running on port {port}")

        self._show_qr(url)

        self._append_log(f"[OK] Server running at {url}")
        self._append_log(f"[OK] Shared folder: {os.path.abspath(self._folder_var.get())}")
        if pin:
            self._append_log("[PIN] PIN protection enabled.")
        else:
            self._append_log("[OPEN] No PIN — anyone on the LAN can access files.")

    def _on_server_start_failed(self, error):
        self._append_log(f"❌ Failed to start: {error}")
        if "address already in use" in error.lower() or "access" in error.lower():
            self._append_log("💡 Port may be in use. Try a different port.")
        self._reset_server_state()

    def _on_stop(self):
        self._stop_server()

    def _stop_server(self):
        if self._flask_server is None:
            return

        self._append_log("Stopping server...")
        self._flask_server.transfer_logger.remove_listener(self._on_log_entry)

        def _stop_thread():
            try:
                self._flask_server.stop()
            except Exception:
                pass
            self.root.after(0, self._on_server_stopped)

        threading.Thread(target=_stop_thread, daemon=True, name="stop-server-thread").start()

    def _on_server_stopped(self):
        self._flask_server = None
        self._reset_server_state()
        self._append_log("⏹ Server stopped.")

    def _reset_server_state(self):
        self._status_dot.itemconfig(self._dot_oval, fill=C_RED)
        self._status_text.config(text="Stopped")
        self._url_label.config(text="—")
        self._status_bar_text.config(text="Ready")
        self._hide_qr()
        self._set_config_enabled(True)

    def _set_config_enabled(self, enabled):
        state = tk.NORMAL if enabled else tk.DISABLED
        self._folder_entry.config(state=state)
        self._port_entry.config(state=state)
        self._pin_entry.config(state=state)
        self._start_btn.config(state=state)
        self._stop_btn.config(state=tk.NORMAL if not enabled else tk.DISABLED)

    def _on_browse(self):
        current = self._folder_var.get()
        chosen = filedialog.askdirectory(
            title="Select Shared Folder",
            initialdir=current if os.path.isdir(current) else os.path.expanduser("~"),
        )
        if chosen:
            self._folder_var.set(chosen)

    def _on_url_click(self, event=None):
        url = self._url_label.cget("text")
        if url and url != "—" and url.startswith("http"):
            try:
                webbrowser.open(url)
            except Exception:
                pass

    def _on_clear_log(self):
        self._log_text.config(state=tk.NORMAL)
        self._log_text.delete("1.0", tk.END)
        self._log_text.config(state=tk.DISABLED)
        if self._flask_server:
            self._flask_server.transfer_logger.clear()

    # -- QR code --

    def _show_qr(self, url):
        try:
            import qrcode as _qr
            img = _qr.make(url)

            if _PIL_AVAILABLE:
                img = img.resize((150, 150), PilImage.NEAREST)
                photo = ImageTk.PhotoImage(img)
                self._qr_image_label.config(image=photo, text="")
                self._qr_image_label._photo = photo  # prevent GC
            else:
                self._qr_image_label.config(text="[QR — install Pillow to see image]")

            self._qr_url_label.config(text=url)
            self._qr_frame.pack(fill=tk.X, pady=(0, 8),
                                before=self._qr_frame.master.children.get("!labelframe2") or self._qr_frame)
        except Exception as exc:
            self._append_log(f"QR generation failed: {exc}")

    def _hide_qr(self):
        try:
            self._qr_frame.pack_forget()
        except Exception:
            pass

    # -- logging --

    def _on_log_entry(self, entry):
        """Called from server threads — hops to the Tk thread via .after()."""
        self.root.after(0, lambda: self._append_log(str(entry)))

    def _append_log(self, message):
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {message}\n"

        self._log_text.config(state=tk.NORMAL)
        self._log_text.insert(tk.END, line)
        self._log_text.see(tk.END)
        self._log_text.config(state=tk.DISABLED)

    # -- window lifecycle / tray integration --

    def _on_close(self):
        """X button pressed — hide to tray unless we're actually quitting."""
        if self._is_closing_for_real:
            self._do_real_close()
            return

        self.root.withdraw()

        if not self._has_shown_tray_hint:
            self._has_shown_tray_hint = True
            self._append_log("💡 Penless is running in the system tray. Right-click the tray icon to exit.")

    def show(self):
        """Bring the window back from the tray."""
        self.root.deiconify()
        self.root.state("normal")
        self.root.lift()
        self.root.focus_force()

    def request_close(self):
        """Called by the tray 'Exit' item — this one actually shuts down."""
        self._is_closing_for_real = True
        self._do_real_close()

    def _do_real_close(self):
        if self._flask_server:
            try:
                self._flask_server.transfer_logger.remove_listener(self._on_log_entry)
                self._flask_server.stop()
            except Exception:
                pass
        self.root.destroy()

        if self._on_exit_requested:
            self._on_exit_requested()
