# Penless — Python Edition 📡

> Local file transfer app — Python port of the original C# WPF + ASP.NET Core app.

Other devices connect via their browser at `http://<your-ip>:8080` — no installs needed on client devices.

---

## Prerequisites

- **Python 3.10+** (download from [python.org](https://www.python.org/downloads/))
- All client devices need only a web browser

---

## Setup (Windows)

```powershell
# 1. Navigate to the python folder
cd d:\Penless\python

# 2. (Recommended) Create a virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the application
python main.py
```

---

## Usage

1. **Launch** `python main.py`
2. Optionally set a **Shared Folder**, **Port**, and **PIN** in the UI
3. Click **▶ Start Server**
4. On another device on the same Wi-Fi or LAN:
   - Open a browser and go to the **URL** shown (e.g. `http://192.168.1.42:8080`)
5. Upload, browse, and download files freely
6. **Minimize** the window to hide it to the system tray (right-click tray icon to Exit)

---

## Configuration

| Setting | Default | Description |
|---|---|---|
| Shared Folder | `SharedFiles` (next to main.py) | Folder that clients can see and upload to |
| Port | `8080` | HTTP port for the server |
| PIN | *(empty)* | Leave empty for open access; set to restrict |
| Max Upload Size | 2 GB | Hard-coded in config.py |

---

## Project Structure

```
python/
├── main.py                    # Entry point (replaces App.xaml.cs)
├── config.py                  # Settings dataclass (replaces AppSettings.cs)
├── requirements.txt           # Python dependencies
├── desktop/
│   ├── app.py                 # Tkinter main window (replaces MainWindow.xaml + .cs)
│   └── tray.py                # pystray system tray (replaces NotifyIcon in App.xaml.cs)
├── server/
│   ├── flask_app.py           # Flask + Waitress factory (replaces Program.cs / Kestrel)
│   ├── endpoints.py           # All API routes (replaces FileEndpoints.cs + StatusEndpoints.cs)
│   ├── middleware.py           # PIN auth (replaces SecurityMiddleware.cs)
│   └── static/                # Browser UI — copied from wwwroot/ (unchanged)
│       ├── index.html
│       ├── css/style.css
│       └── js/app.js
└── services/
    ├── file_service.py        # File operations (replaces FileService.cs)
    ├── network_service.py     # IP detection (replaces NetworkService.cs)
    └── transfer_logger.py     # Log ring buffer (replaces TransferLogger.cs)
```

---

## C# → Python Mapping

| C# File | Python Equivalent |
|---|---|
| `App.xaml.cs` (lifecycle, tray) | `main.py` + `desktop/tray.py` |
| `MainWindow.xaml` + `.cs` | `desktop/app.py` |
| `Program.cs` (ServerBootstrap) | `server/flask_app.py` |
| `FileEndpoints.cs` | `server/endpoints.py` |
| `StatusEndpoints.cs` | `server/endpoints.py` |
| `SecurityMiddleware.cs` | `server/middleware.py` |
| `FileService.cs` | `services/file_service.py` |
| `NetworkService.cs` | `services/network_service.py` |
| `TransferLogger.cs` | `services/transfer_logger.py` |
| `AppSettings.cs` | `config.py` |
| `wwwroot/` | `server/static/` (identical files) |

---

## Dependency Mapping

| .NET / C# | Python |
|---|---|
| ASP.NET Core / Kestrel | Flask + Waitress |
| WPF (XAML) | Tkinter |
| `System.Windows.Forms.NotifyIcon` | pystray |
| `QRCoder` NuGet | `qrcode[pil]` |
| `System.Net.NetworkInformation` | `socket` stdlib |
| `System.IO` | `os`, `shutil` stdlib |
| CORS middleware | `flask-cors` |
| `System.Collections.Concurrent.ConcurrentQueue` | `collections.deque` + `threading.Lock` |

---

## Security Notes (same as original)

- All file paths are **validated** to stay within the shared folder (directory traversal prevention)
- Filenames are **sanitized** to remove dangerous characters  
- The server only listens on your **local network** — not exposed to the internet
- The PIN is stored in memory only — it's for casual access control, not enterprise security

---

## Optional: Build a Single EXE

```powershell
pip install pyinstaller
pyinstaller --onefile --windowed --icon=app.ico --name=Penless `
    --add-data "server/static;server/static" `
    main.py
# Output: dist/Penless.exe
```
