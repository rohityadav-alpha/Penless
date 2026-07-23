"""
REST API endpoints for Penless.

All routes live under /api/ and are registered as a Flask Blueprint.
The browser frontend (index.html / app.js) talks to these.
"""

import io
import os

import qrcode
from flask import Blueprint, jsonify, request, send_file, current_app

from services.file_service import FileService
from services.network_service import NetworkService
from services.transfer_logger import TransferLogger
from config import PenlessSettings

api_bp = Blueprint("api", __name__, url_prefix="/api")


# -- helpers to grab services from app config --

def _fs():
    return current_app.config["FILE_SERVICE"]

def _logger():
    return current_app.config["TRANSFER_LOGGER"]

def _net():
    return current_app.config["NETWORK_SERVICE"]

def _settings():
    return current_app.config["PENLESS_SETTINGS"]


# ===== status endpoints =====

@api_bp.route("/status", methods=["GET"])
def get_status():
    """Basic server info — always accessible, no PIN needed."""
    settings = _settings()
    net = _net()
    ip = net.get_local_ip_address()
    port = settings.port

    return jsonify({
        "status": "running",
        "localIp": ip,
        "port": port,
        "url": f"http://{ip}:{port}",
        "sharedFolder": os.path.abspath(settings.shared_folder),
        "pinRequired": bool(settings.pin),
        "maxUploadSize": settings.max_upload_size_bytes,
        "maxUploadSizeFormatted": _format_size(settings.max_upload_size_bytes),
        "networkAvailable": net.is_network_available(),
    })


@api_bp.route("/auth", methods=["POST"])
def authenticate():
    """Validate the PIN. Body: { "pin": "1234" }"""
    settings = _settings()
    if not settings.pin:
        return jsonify({"authenticated": True, "message": "No PIN required."})

    body = request.get_json(silent=True) or {}
    if body.get("pin", "") == settings.pin:
        return jsonify({"authenticated": True})

    return jsonify({"authenticated": False, "error": "Incorrect PIN."}), 401


@api_bp.route("/qrcode", methods=["GET"])
def get_qrcode():
    """Generate a QR code PNG pointing to the server URL."""
    settings = _settings()
    ip = _net().get_local_ip_address()
    url = f"http://{ip}:{settings.port}"

    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png", download_name="penless-qr.png")


@api_bp.route("/logs", methods=["GET"])
def get_logs():
    """Return recent activity log entries."""
    count = request.args.get("count", 50, type=int)
    entries = _logger().get_recent(count)
    return jsonify({"entries": [e.to_dict() for e in entries]})


# ===== file endpoints =====

@api_bp.route("/files", methods=["GET"])
def browse_files():
    """List files and folders at a given path."""
    relative_path = request.args.get("path", "")
    result = _fs().browse(relative_path)

    if result.error:
        return jsonify({"error": result.error}), 404
    return jsonify(result.to_dict())


@api_bp.route("/files/download", methods=["GET"])
def download_file():
    """Download a single file. Supports range requests for big files."""
    path = request.args.get("path", "").strip()
    if not path:
        return jsonify({"error": "File path is required."}), 400

    full_path = _fs().get_file_path(path)
    if full_path is None:
        return jsonify({"error": "File not found or access denied."}), 404

    client_ip = request.remote_addr or "unknown"
    file_name = os.path.basename(full_path)
    size = os.path.getsize(full_path)
    _logger().log("DOWNLOAD", f"{file_name} ({_format_size(size)})", client_ip)

    mime = _get_content_type(file_name)
    return send_file(full_path, mimetype=mime, as_attachment=True,
                     download_name=file_name, conditional=True)


@api_bp.route("/upload", methods=["POST"])
def upload_files():
    """Accept one or more files via multipart form upload."""
    client_ip = request.remote_addr or "unknown"
    max_size = _settings().max_upload_size_bytes
    target_folder = request.args.get("folder", "")

    uploaded_files = request.files.getlist("files")
    results = []

    for f in uploaded_files:
        if not f or f.filename == "":
            continue

        # check file size
        f.seek(0, 2)
        file_size = f.tell()
        f.seek(0)

        if file_size > max_size:
            results.append({
                "name": f.filename,
                "error": f"File exceeds maximum size of {_format_size(max_size)}."
            })
            continue

        try:
            save_result = _fs().save_file(f.stream, f.filename, target_folder)
            if save_result.success:
                _logger().log("UPLOAD", f"{save_result.file_name} ({_format_size(save_result.size)})", client_ip)
                results.append({
                    "name": save_result.file_name,
                    "size": save_result.size,
                    "sizeFormatted": _format_size(save_result.size),
                    "path": save_result.path,
                })
            else:
                results.append({"name": f.filename, "error": save_result.error})
        except Exception as exc:
            _logger().log("UPLOAD_ERROR", f"{f.filename}: {exc}", client_ip)
            results.append({"name": f.filename, "error": "Upload failed. Please try again."})

    return jsonify({"uploaded": len([r for r in results if "error" not in r]), "files": results})


@api_bp.route("/files", methods=["PATCH"])
def rename_item():
    """Rename a file or folder."""
    client_ip = request.remote_addr or "unknown"
    path = request.args.get("path", "")
    new_name = request.args.get("newName", "")

    result = _fs().rename(path, new_name)
    if result is None:
        return jsonify({"error": "Invalid name or path, or destination already exists."}), 400

    _logger().log("RENAME", f"{path} → {result}", client_ip)
    return jsonify({"newPath": result})


@api_bp.route("/files", methods=["DELETE"])
def delete_file():
    """Delete a file."""
    client_ip = request.remote_addr or "unknown"
    path = request.args.get("path", "")

    if _fs().delete_file(path):
        _logger().log("DELETE", path, client_ip)
        return jsonify({"deleted": path})

    return jsonify({"error": "File not found or access denied."}), 404


@api_bp.route("/folders", methods=["POST"])
def create_folder():
    """Create a new folder."""
    client_ip = request.remote_addr or "unknown"
    path = request.args.get("path", "")
    name = request.args.get("name", "")

    result = _fs().create_folder(path, name)
    if result is None:
        return jsonify({"error": "Invalid folder name."}), 400

    _logger().log("CREATE_FOLDER", result, client_ip)
    return jsonify({"path": result})


@api_bp.route("/folders", methods=["DELETE"])
def delete_folder():
    """Delete a folder and everything inside it."""
    client_ip = request.remote_addr or "unknown"
    path = request.args.get("path", "")

    if _fs().delete_folder(path):
        _logger().log("DELETE_FOLDER", path, client_ip)
        return jsonify({"deleted": path})

    return jsonify({"error": "Folder not found or access denied."}), 404


# ===== helpers =====

def _format_size(size_bytes):
    """Turn byte count into something humans can read."""
    sizes = ["B", "KB", "MB", "GB", "TB"]
    value = float(size_bytes)
    order = 0
    while value >= 1024 and order < len(sizes) - 1:
        order += 1
        value /= 1024
    formatted = f"{value:.2f}".rstrip("0").rstrip(".")
    return f"{formatted} {sizes[order]}"


def _get_content_type(file_name):
    """Map file extension → MIME type."""
    ext = os.path.splitext(file_name)[1].lower()
    mime_map = {
        ".pdf":  "application/pdf",
        ".zip":  "application/zip",
        ".rar":  "application/x-rar-compressed",
        ".7z":   "application/x-7z-compressed",
        ".tar":  "application/x-tar",
        ".gz":   "application/gzip",
        ".jpg":  "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png":  "image/png",
        ".gif":  "image/gif",
        ".svg":  "image/svg+xml",
        ".webp": "image/webp",
        ".mp4":  "video/mp4",
        ".mp3":  "audio/mpeg",
        ".wav":  "audio/wav",
        ".txt":  "text/plain",
        ".csv":  "text/csv",
        ".json": "application/json",
        ".xml":  "application/xml",
        ".html": "text/html",
        ".htm":  "text/html",
        ".css":  "text/css",
        ".js":   "application/javascript",
        ".doc":  "application/msword",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xls":  "application/vnd.ms-excel",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".ppt":  "application/vnd.ms-powerpoint",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".exe":  "application/x-msdownload",
        ".iso":  "application/x-iso9660-image",
    }
    return mime_map.get(ext, "application/octet-stream")
