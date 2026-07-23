"""
PIN-based security middleware for Flask.

Checks the X-Pin header or ?pin= query param on every /api/ request.
/api/auth and /api/status are always accessible without a PIN.
"""

from flask import request, jsonify


PUBLIC_PATHS = ("/api/auth", "/api/status")


def pin_required(settings, logger):
    """
    Returns a before_request hook that enforces PIN auth.

    Usage:
        app.before_request(pin_required(settings, logger))
    """
    def check_pin():
        path = request.path
        client_ip = request.remote_addr or "unknown"

        # log all API requests
        if path.startswith("/api/"):
            logger.log("REQUEST", f"{request.method} {path}", client_ip)

        if settings.pin and path.startswith("/api/"):
            is_public = any(path.lower().startswith(p) for p in PUBLIC_PATHS)
            if not is_public:
                provided_pin = request.headers.get("X-Pin") or request.args.get("pin")
                if provided_pin != settings.pin:
                    logger.log("AUTH_FAIL", f"Invalid PIN for {path}", client_ip)
                    return jsonify({"error": "Invalid PIN. Please enter the correct PIN to access files."}), 401

    return check_pin
