# Penless — Tech Stack & Architecture Reference

> Complete breakdown of every technology, framework, library, and design pattern used in the .NET application.

---

## Table of Contents

1. [Runtime & SDK](#1-runtime--sdk)
2. [Projects & Build System](#2-projects--build-system)
3. [Desktop Layer — WPF + WinForms](#3-desktop-layer--wpf--winforms)
4. [Web Server Layer — ASP.NET Core](#4-web-server-layer--aspnet-core)
5. [NuGet Packages](#5-nuget-packages)
6. [Frontend (Browser UI)](#6-frontend-browser-ui)
7. [C# Language Features Used](#7-c-language-features-used)
8. [Architecture & Design Patterns](#8-architecture--design-patterns)
9. [Security Model](#9-security-model)
10. [File-by-File Reference](#10-file-by-file-reference)

---

## 1. Runtime & SDK

| Item | Value |
|---|---|
| **Runtime** | .NET 8.0 (LTS) |
| **Desktop SDK** | `Microsoft.NET.Sdk` (net8.0-windows) |
| **Server SDK** | `Microsoft.NET.Sdk.Web` (net8.0) |
| **Language** | C# 12 |
| **Nullable refs** | Enabled (`<Nullable>enable</Nullable>`) |
| **Implicit usings** | Enabled |
| **Output type (Desktop)** | `WinExe` — no console window |
| **Output type (Server)** | `Library` — hosted inside the Desktop process |

---

## 2. Projects & Build System

The solution has **two projects** — the server is a library, the desktop is the host:

```
Penless/
├── src/
│   ├── Penless.Desktop/       ← WinExe — the thing users launch
│   │   └── → references Penless.Server
│   └── Penless.Server/        ← Library — ASP.NET Core embedded server
└── publish.ps1                ← PowerShell self-contained publish script
```

### Why two projects?

The server is a separate library so it can be unit tested independently without a GUI, and potentially reused in a future CLI or service wrapper.

### Build targets (MSBuild custom targets)

The Desktop `.csproj` defines two custom MSBuild targets to copy the browser UI (`wwwroot/`) into the output directory at build and publish time — since WPF can't automatically pull content from a referenced library's wwwroot:

```xml
<Target Name="CopyWwwrootToBin" AfterTargets="Build">
<Target Name="CopyWwwrootToPublish" AfterTargets="Publish">
```

---

## 3. Desktop Layer — WPF + WinForms

### WPF (Windows Presentation Foundation)

The main application window is built with **WPF** (`<UseWPF>true</UseWPF>`).

| WPF Component | Where used |
|---|---|
| `Application` (App.xaml / App.xaml.cs) | App lifecycle, tray icon initialization, clean shutdown |
| `Window` (MainWindow.xaml / .cs) | Main UI window |
| `Grid` with `RowDefinitions` | Top-level layout (title bar / content / status bar) |
| `ScrollViewer` | Scrollable content area |
| `StackPanel` | Vertical stacking of UI sections |
| `DockPanel` | Folder row (entry + Browse button side by side) |
| `Border` with `LinearGradientBrush` | Win98-style raised panels and the navy title bar |
| `TextBlock` | All read-only labels and the clickable URL |
| `TextBox` | Shared folder path, port number inputs |
| `PasswordBox` | PIN entry (`MaxLength="10"`) |
| `Button` with custom `Style` | Start Server, Stop Server, Browse, Clear |
| `Ellipse` (`StatusDot`) | Red/green status indicator |
| `Image` (`QrImage`) | QR code display |
| `Rectangle` | 1px separator lines (Win98 groove effect) |
| `XAML Resources` | `CardBorder`, `SectionTitle`, `InfoLabel`, `InfoValue`, `ModernButton`, `DangerButton`, `SecondaryButton`, `ModernTextBox`, `ModernPasswordBox` styles |
| `LinearGradientBrush` | Title bar gradient (`#000080` → `#1084D0`) and panel border chamfers |
| `BitmapImage` with `MemoryStream` | Loading the QR code PNG bytes into a WPF `ImageSource` |
| `Dispatcher.Invoke` | Marshalling log updates from the server thread back to the UI thread |
| `OpenFolderDialog` (Microsoft.Win32) | "Browse..." folder picker dialog |
| `WindowState` + `Hide()` / `Show()` | Minimize-to-tray behavior |
| `StateChanged` event | Detecting window minimize to trigger tray hiding |
| `Closing` event (`CancelEventArgs`) | Intercepting the X button to hide instead of quit |
| `Loaded` event | Initial setup (detect IP, set default folder) |

### WinForms (System.Windows.Forms)

Used **only** for the system tray icon (`<UseWindowsForms>true</UseWindowsForms>`). WPF has no built-in system tray support.

| WinForms Component | Where used |
|---|---|
| `NotifyIcon` | The tray icon itself — sets `Text`, `Icon`, `Visible` |
| `ContextMenuStrip` | Right-click menu on the tray icon |
| `ToolStripMenuItem` | "Open Penless" (bold) and "Exit" items |
| `ToolStripSeparator` | Visual divider between menu items |
| `SystemIcons.Application` | Default Windows app icon for the tray |
| `Font` with `FontStyle.Bold` | Makes "Open Penless" bold in the tray menu |

> **Note:** Both WPF and WinForms are active in the same process. The `Application` alias is needed to disambiguate `System.Windows.Application` from `System.Windows.Forms.Application`.

---

## 4. Web Server Layer — ASP.NET Core

The embedded HTTP server is built entirely on **ASP.NET Core Minimal APIs** (no controllers, no MVC).

### Core ASP.NET Core components

| Component | How it's used |
|---|---|
| `WebApplication.CreateBuilder()` | Bootstraps the DI container and host |
| `WebApplicationOptions` | Sets `ContentRootPath` and `WebRootPath` at runtime |
| **Kestrel** | The embedded HTTP server — `ListenAnyIP(port)` binds to all interfaces |
| `builder.WebHost.ConfigureKestrel()` | Sets upload size limit (2 GB), header timeout (5 min), keep-alive (10 min) |
| `app.UseStaticFiles()` | Serves `wwwroot/` (HTML, CSS, JS) |
| `app.UseDefaultFiles()` | Makes `index.html` the default document at `/` |
| `app.MapFallbackToFile("index.html")` | SPA fallback — any unknown path returns index.html |
| `app.UseCors()` | Allows all origins/methods/headers for LAN access |
| `app.UseMiddleware<T>()` | Registers `SecurityMiddleware` in the pipeline |
| `app.MapGroup("/api")` | Groups all API routes under the `/api` prefix |
| `app.StartAsync()` / `app.StopAsync()` | Non-blocking server lifecycle managed from WPF |
| `app.WaitForShutdownAsync()` | Background task that detects server errors |

### Minimal API endpoints

All routes are defined as lambda-style Minimal API handlers — no controller classes:

| Method | Route | Handler |
|---|---|---|
| `GET` | `/api/status` | Server info, IP, port, PIN status |
| `POST` | `/api/auth` | PIN validation |
| `GET` | `/api/qrcode` | QR code PNG (uses QRCoder) |
| `GET` | `/api/logs` | Recent transfer log entries |
| `GET` | `/api/files` | Browse shared folder |
| `GET` | `/api/files/download` | Download a file (with range support) |
| `POST` | `/api/upload` | Upload files (multipart/form-data) |
| `POST` | `/api/folders` | Create a folder |
| `DELETE` | `/api/files` | Delete a file |
| `DELETE` | `/api/folders` | Delete a folder (recursive) |
| `PATCH` | `/api/files` | Rename a file or folder |

### Dependency Injection

Services are registered as **singletons** (one instance for the app lifetime):

```csharp
builder.Services.AddSingleton(new FileService(sharedPath));
builder.Services.AddSingleton(new TransferLogger(settings.MaxLogEntries));
builder.Services.AddSingleton<NetworkService>();
```

Settings are injected via `IOptions<PenlessSettings>` (the Options pattern).

### Middleware pipeline order

```
Request →
  UseCors()                  // CORS headers
  UseMiddleware<Security>()  // PIN check + request logging
  UseDefaultFiles()          // index.html default
  UseStaticFiles()           // wwwroot serving
  MapFileEndpoints()         // /api/files, /api/upload, etc.
  MapStatusEndpoints()       // /api/status, /api/auth, /api/qrcode, /api/logs
  MapFallbackToFile()        // SPA catch-all
→ Response
```

### FormOptions — large upload support

```csharp
builder.Services.Configure<FormOptions>(options =>
    options.MultipartBodyLengthLimit = settings.MaxUploadSizeBytes);
```

This is required alongside the Kestrel limit to allow large multipart uploads through ASP.NET Core's form binding.

---

## 5. NuGet Packages

### QRCoder `v1.6.0`

Used in **both** projects.

| Class | Where |
|---|---|
| `QRCodeGenerator` | Creates the raw QR data matrix from a URL string |
| `QRCodeGenerator.ECCLevel.M` | Medium error correction (15% data restoration) |
| `PngByteQRCode` | Renders the QR matrix to a raw PNG byte array |
| `qrCode.GetGraphic(8)` | Pixel size 8 = each QR module is 8×8 pixels |

- In `StatusEndpoints.cs` → QR code API endpoint (`/api/qrcode`) returns PNG bytes
- In `MainWindow.xaml.cs` → QR code is decoded from bytes into a `BitmapImage` and shown in the `<Image>` control

No external PNG rendering library is needed — QRCoder outputs raw PNG bytes directly.

---

## 6. Frontend (Browser UI)

The client-side UI lives in `wwwroot/` and is served as static files by Kestrel. No framework, no build step.

| File | Technology | Purpose |
|---|---|---|
| `index.html` | Plain HTML5 | Single-page app shell |
| `css/style.css` | Vanilla CSS | Win98 retro theme (CSS custom properties, grid, flexbox) |
| `js/app.js` | Vanilla JavaScript (ES2020+) | All interactivity — no frameworks |

### JavaScript features used (`app.js`)

- `fetch()` API for all REST calls
- `FormData` for file uploads with progress tracking (`XMLHttpRequest.upload.onprogress`)
- `async/await` throughout
- `URL` + `URLSearchParams` for building API URLs
- `localStorage` for persisting the PIN across page reloads
- `DragEvent` / `dragover` / `drop` for drag-and-drop upload zones
- `Blob` + `URL.createObjectURL()` for client-side download triggering
- Dynamic DOM manipulation (`createElement`, `innerHTML`, `classList`)
- `window.history.pushState` for breadcrumb navigation without page reloads

### CSS features (`style.css`)

- CSS custom properties (`--win-gray`, `--win-navy`, etc.) for the Win98 palette
- CSS Grid and Flexbox for layout
- `box-shadow` with inset values to simulate the 3D bevel look
- `:hover` and `:active` transitions for button feedback
- `@keyframes` for the upload progress animation
- `scrollbar-width` / `::-webkit-scrollbar` for styled scrollbars

---

## 7. C# Language Features Used

| Feature | Where |
|---|---|
| **Top-level namespaces** (`namespace Penless.Desktop;`) | All files |
| **Nullable reference types** (`string?`, `WebApplication?`) | All files |
| **`init`-only properties** | `BrowseResult`, `FileItem`, `FolderItem`, `SaveResult`, `LogEntry` |
| **Collection expressions** (`[]`) | `Folders = []`, `sizes = ["B", "KB", ...]` |
| **Pattern matching** (`is > 0 and < 65536`) | Port validation in MainWindow.xaml.cs |
| **Switch expressions** | `GetContentType()` in FileEndpoints.cs |
| **Source-generated Regex** (`[GeneratedRegex(...)]`) | `MultiUnderscoreRegex()` in FileService.cs — compile-time regex, no runtime overhead |
| **`partial` class + `partial` method** | `FileService` uses `partial` for the generated regex |
| **Lambda event handlers** (`(_, _) =>`) | Tray menu clicks in App.xaml.cs |
| **Discard `_`** | `_ = Task.Run(...)` in MainWindow.xaml.cs |
| **`await using`** | `FileStream` in `SaveFileAsync` |
| **Range operator (`[..255]`)** | Filename truncation in SanitizeFileName |
| **Interpolated strings** | Throughout (log messages, URLs, paths) |
| **`CancellationTokenSource` with timeout** | `StopServer` (5-second graceful shutdown) |
| **`StringComparison.OrdinalIgnoreCase`** | All path boundary checks |
| **`sealed` classes** | All service and model classes |
| **`static` extension methods** | `MapFileEndpoints()`, `MapStatusEndpoints()` on `WebApplication` |
| **`IReadOnlyList<T>`** | `TransferLogger.GetRecent()` return type |
| **`ConcurrentQueue<T>`** | Thread-safe log queue in TransferLogger |
| **`Task.Run` + fire-and-forget** | Background server monitoring |
| **`Path.GetFullPath`** | Path canonicalization for traversal prevention |

---

## 8. Architecture & Design Patterns

### Dual-process pattern (embedded server in desktop host)

ASP.NET Core runs **inside** the WPF process — no separate server process. The `ServerBootstrap.CreateServer()` factory returns a configured `WebApplication` but doesn't start it; the WPF host calls `StartAsync()` and `StopAsync()` as needed.

```
[Penless.exe process]
  ├── WPF UI thread (main thread)
  ├── Kestrel I/O threads (background)
  │     └── handles HTTP requests
  └── ASP.NET thread pool workers
        └── runs endpoint lambdas
```

### Service pattern

- `FileService` — all file I/O goes through this single class, never directly from endpoints
- `NetworkService` — IP detection isolated from the rest of the app
- `TransferLogger` — logging isolated behind a clean interface with events

### Options pattern (`IOptions<T>`)

Settings flow from the WPF UI → `PenlessSettings` POCO → registered with DI via `Configure<PenlessSettings>()` → injected as `IOptions<PenlessSettings>` into endpoints and middleware.

### Event-driven UI updates

`TransferLogger` fires a C# `event Action<LogEntry>` for each new log entry. `MainWindow` subscribes when the server starts and unsubscribes when it stops. The handler uses `Dispatcher.Invoke` to marshal the update to the WPF UI thread.

### Minimize-to-tray

Window closing is **intercepted** (`e.Cancel = true`) and replaced with `Hide()`. A flag `_isClosingForReal` distinguishes between "user pressed X" (hide to tray) and "Exit was chosen from tray menu" (real shutdown).

### Security: defense in depth

Path traversal is prevented at two levels:
1. **Input rejection** — `..` and null bytes rejected immediately
2. **Canonical path check** — `Path.GetFullPath()` resolves symlinks and `..` segments, then `StartsWith(_rootPath)` verifies the result is inside the boundary

---

## 9. Security Model

| Threat | Mitigation |
|---|---|
| Directory traversal | `ResolveSafePath()` — reject `..`, then canonicalize and boundary-check |
| Malicious filenames | `SanitizeFileName()` — strip invalid chars, trim dots/spaces, collapse underscores, cap at 255 chars |
| Unauthorized access | `SecurityMiddleware` — checks `X-Pin` header or `?pin=` query param before allowing any `/api/` call |
| Public endpoint bypass | `/api/auth` and `/api/status` are always public (PIN check skipped) |
| File overwrite on upload | `GetUniqueFilePath()` — appends `(1)`, `(2)`, ... if the file already exists |
| Root folder deletion | `DeleteFolder()` refuses to delete if `relativePath` is empty or equals root |
| Large upload denial-of-service | Upload size capped at 2 GB in both Kestrel and FormOptions |

---

## 10. File-by-File Reference

### `Penless.Desktop/`

| File | Technology | Role |
|---|---|---|
| `App.xaml` | WPF XAML | Application-level resource dictionary, startup window declaration |
| `App.xaml.cs` | C# / WinForms | `NotifyIcon` tray setup, application lifecycle (`OnStartup`, `OnExit`) |
| `MainWindow.xaml` | WPF XAML | All UI layout — title bar, status section, QR panel, config section, log panel, status bar |
| `MainWindow.xaml.cs` | C# / ASP.NET Core | Server lifecycle, event handlers, QR generation, log display, tray behavior |
| `Penless.Desktop.csproj` | MSBuild / SDK | Target frameworks, WPF+WinForms flags, icon, QRCoder reference, custom wwwroot copy targets |
| `app.ico` | Win32 icon | Application icon (title bar, taskbar, tray fallback) |
| `AssemblyInfo.cs` | C# attributes | Assembly metadata |

### `Penless.Server/`

| File | Technology | Role |
|---|---|---|
| `Program.cs` | ASP.NET Core | `ServerBootstrap.CreateServer()` — DI, Kestrel, middleware pipeline, endpoint registration |
| `Configuration/AppSettings.cs` | C# | `PenlessSettings` POCO — strongly-typed settings with defaults |
| `Services/FileService.cs` | C# / `System.IO` | All file operations: browse, upload, download, rename, delete, path safety |
| `Services/NetworkService.cs` | C# / `System.Net` | LAN IP detection via `NetworkInterface` + UDP fallback |
| `Services/TransferLogger.cs` | C# / `ConcurrentQueue` | Thread-safe ring buffer for activity log, `event Action<LogEntry>` |
| `Middleware/SecurityMiddleware.cs` | ASP.NET Core middleware | PIN validation (`X-Pin` header / `?pin=` query), request logging |
| `Endpoints/FileEndpoints.cs` | Minimal API | 7 file/folder endpoints: browse, download, upload, create, delete (file+folder), rename |
| `Endpoints/StatusEndpoints.cs` | Minimal API + QRCoder | 4 status endpoints: status, auth, QR code, logs |
| `appsettings.json` | JSON | Default config (port 8080, 2 GB limit) |
| `Penless.Server.csproj` | MSBuild | Library output type, QRCoder NuGet, wwwroot content items |

### `wwwroot/`

| File | Technology | Role |
|---|---|---|
| `index.html` | HTML5 | SPA shell — all UI sections present, shown/hidden by JS |
| `css/style.css` | CSS3 | Win98 retro theme, CSS custom properties, responsive layout |
| `js/app.js` | ES2020 JavaScript | All client logic — fetch API, drag-drop, progress, PIN, breadcrumbs, folder nav |
