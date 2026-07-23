from dataclasses import dataclass


@dataclass
class PenlessSettings:
    """App-wide settings passed from the GUI to the server."""

    shared_folder: str = "SharedFiles"
    port: int = 8080
    pin: str = ""  # empty = open access, no auth needed
    max_upload_size_bytes: int = 2 * 1024 * 1024 * 1024  # 2 GB
    max_log_entries: int = 500
