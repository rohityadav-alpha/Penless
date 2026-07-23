"""
Flask app factory + server lifecycle management.

Creates the Flask application with CORS, PIN middleware, API routes,
and static file serving. Uses Waitress as the WSGI server — runs in a
background thread so the Tkinter GUI stays responsive.
"""

import os
import sys
import threading
import logging
from typing import Optional


def get_base_dir():
    """
    Where bundled resources live.
    PyInstaller --onefile extracts to a temp dir (sys._MEIPASS);
    otherwise it's just the directory this file sits in.
    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

from flask import Flask, send_from_directory
from flask_cors import CORS

from config import PenlessSettings
from services.file_service import FileService
from services.network_service import NetworkService
from services.transfer_logger import TransferLogger
from server.middleware import pin_required
from server.endpoints import api_bp

# keep Flask/Werkzeug quiet — we have our own activity log
log = logging.getLogger("werkzeug")
log.setLevel(logging.WARNING)


class FlaskServer:
    """Wraps the Flask app + Waitress server. Call start() and stop()."""

    def __init__(self, settings: PenlessSettings, content_root: Optional[str] = None):
        self.settings = settings
        self._thread = None
        self._server = None  # waitress instance

        if os.path.isabs(settings.shared_folder):
            shared_path = settings.shared_folder
        else:
            base = content_root or os.path.dirname(os.path.abspath(sys.argv[0]))
            shared_path = os.path.join(base, settings.shared_folder)

        self.file_service = FileService(shared_path)
        self.transfer_logger = TransferLogger(settings.max_log_entries)
        self.network_service = NetworkService()

        self._app = self._create_app(content_root)

    def _create_app(self, content_root):
        # static files (the browser UI) are in server/static/
        static_dir = os.path.join(get_base_dir(), "server", "static")
        if not os.path.isdir(static_dir):
            static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

        app = Flask(__name__, static_folder=static_dir, static_url_path="")

        # stash services in app config so endpoints can grab them
        app.config["FILE_SERVICE"] = self.file_service
        app.config["TRANSFER_LOGGER"] = self.transfer_logger
        app.config["NETWORK_SERVICE"] = self.network_service
        app.config["PENLESS_SETTINGS"] = self.settings
        app.config["MAX_CONTENT_LENGTH"] = self.settings.max_upload_size_bytes

        CORS(app)
        app.before_request(pin_required(self.settings, self.transfer_logger))
        app.register_blueprint(api_bp)

        # serve index.html at root and as SPA fallback
        @app.route("/")
        def serve_index():
            return send_from_directory(static_dir, "index.html")

        @app.route("/<path:filename>")
        def serve_static(filename):
            full = os.path.join(static_dir, filename)
            if os.path.isfile(full):
                return send_from_directory(static_dir, filename)
            return send_from_directory(static_dir, "index.html")

        return app

    def start(self):
        """Fire up Waitress in a daemon thread."""
        if self._thread and self._thread.is_alive():
            return

        # try to punch a hole in Windows Firewall so LAN devices can connect
        self._ensure_firewall_rule(self.settings.port)

        import waitress

        def _run():
            self._server = waitress.create_server(
                self._app,
                host="0.0.0.0",
                port=self.settings.port,
                threads=8,
            )
            self._server.run()

        self._thread = threading.Thread(target=_run, daemon=True, name="penless-flask")
        self._thread.start()

    def stop(self):
        """Tell Waitress to shut down."""
        if self._server is not None:
            try:
                self._server.close()
            except Exception:
                pass
            self._server = None

    @property
    def is_running(self):
        return self._thread is not None and self._thread.is_alive()

    @staticmethod
    def _ensure_firewall_rule(port):
        """
        Add a Windows Firewall inbound rule for our port.
        Without this, other devices get ERR_CONNECTION_TIMED_OUT.
        Fails silently if we don't have admin rights — no big deal,
        user can always add it manually.
        """
        import subprocess

        rule_name = f"Penless Port {port}"

        check = subprocess.run(
            ["netsh", "advfirewall", "firewall", "show", "rule", f"name={rule_name}"],
            capture_output=True, text=True,
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )
        if "No rules match" not in check.stdout and rule_name in check.stdout:
            return  # already there

        subprocess.run(
            [
                "netsh", "advfirewall", "firewall", "add", "rule",
                f"name={rule_name}",
                "protocol=TCP", "dir=in",
                f"localport={port}",
                "action=allow",
                "profile=private,domain",
            ],
            capture_output=True,
            creationflags=0x08000000,
        )
