"""
Thread-safe activity logger.

Keeps recent entries in a ring buffer (deque with maxlen).
Supports listener callbacks so the GUI can update in real time.
"""

import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, List, Optional


@dataclass
class LogEntry:
    timestamp: datetime
    action: str
    detail: str
    client_ip: str = "local"

    def __str__(self):
        return f"[{self.timestamp.strftime('%H:%M:%S')}] [{self.action}] {self.detail} (from {self.client_ip})"

    def to_dict(self):
        return {
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "action": self.action,
            "detail": self.detail,
            "clientIp": self.client_ip,
        }


class TransferLogger:
    """
    In-memory log with a capped size. Fires callbacks when new entries come in
    so the desktop UI can pick them up.
    """

    def __init__(self, max_entries=500):
        self._max_entries = max_entries
        self._entries = deque(maxlen=max_entries)
        self._lock = threading.Lock()
        self._callbacks: List[Callable] = []

    def add_listener(self, callback):
        with self._lock:
            self._callbacks.append(callback)

    def remove_listener(self, callback):
        with self._lock:
            try:
                self._callbacks.remove(callback)
            except ValueError:
                pass

    def log(self, action, detail, client_ip=None):
        """Add an entry and notify all listeners."""
        entry = LogEntry(
            timestamp=datetime.now(),
            action=action,
            detail=detail,
            client_ip=client_ip or "local",
        )
        with self._lock:
            self._entries.append(entry)
            callbacks = list(self._callbacks)

        # fire outside the lock to avoid deadlocks
        for cb in callbacks:
            try:
                cb(entry)
            except Exception:
                pass

    def get_recent(self, count=50):
        """Get the last N entries, newest first."""
        with self._lock:
            entries = list(self._entries)
        recent = entries[-count:] if count < len(entries) else entries
        return list(reversed(recent))

    def clear(self):
        with self._lock:
            self._entries.clear()
