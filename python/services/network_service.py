"""
Figures out the local LAN IP address.
Uses the UDP socket trick — connect to an external IP without sending data,
then read which source address the OS picked.
"""

import socket


class NetworkService:

    def get_local_ip_address(self):
        """
        Get the local IPv4 address that other devices on the LAN would use
        to reach this machine. Falls back to 127.0.0.1 if nothing works.
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.settimeout(0)
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            pass

        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"

    def is_network_available(self):
        """Quick check — if we got a real IP (not loopback), we're probably online."""
        return self.get_local_ip_address() != "127.0.0.1"
