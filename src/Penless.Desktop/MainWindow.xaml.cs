using System.Diagnostics;
using System.IO;
using System.Windows;
using System.Windows.Media.Imaging;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Win32;
using Penless.Server;
using Penless.Server.Configuration;
using Penless.Server.Services;
using QRCoder;
using System.ComponentModel;

namespace Penless.Desktop;

public partial class MainWindow : Window
{
    private Microsoft.AspNetCore.Builder.WebApplication? _server;
    private TransferLogger? _logger;
    private readonly NetworkService _networkService = new();

    // these two flags control the minimize-to-tray vs real close behavior
    private bool _hasShownTrayHint;
    private bool _isClosingForReal;

    public MainWindow()
    {
        InitializeComponent();
        StateChanged += OnWindowStateChanged;
    }

    private void Window_Loaded(object sender, RoutedEventArgs e)
    {
        var defaultShared = Path.Combine(AppContext.BaseDirectory, "SharedFiles");
        FolderPathBox.Text = defaultShared;
        Directory.CreateDirectory(defaultShared);

        var ip = _networkService.GetLocalIpAddress();
        IpText.Text = ip;
        AppendLog($"Local IP detected: {ip}");

        if (!_networkService.IsNetworkAvailable())
            AppendLog("⚠ No network connection detected. Other devices won't be able to connect.");
    }

    private async void StartButton_Click(object sender, RoutedEventArgs e)
    {
        if (_server != null)
        {
            AppendLog("Server is already running.");
            return;
        }

        // default to 8080 but accept whatever the user typed
        var port = 8080;
        if (int.TryParse(PortBox.Text.Trim(), out var parsed) && parsed is > 0 and < 65536)
            port = parsed;
        else
        {
            AppendLog("⚠ Invalid port. Using default 8080.");
            PortBox.Text = "8080";
        }

        var sharedFolder = FolderPathBox.Text.Trim();
        if (string.IsNullOrWhiteSpace(sharedFolder))
        {
            sharedFolder = Path.Combine(AppContext.BaseDirectory, "SharedFiles");
            FolderPathBox.Text = sharedFolder;
        }

        var settings = new PenlessSettings
        {
            SharedFolder = sharedFolder,
            Port = port,
            Pin = PinBox.Password.Trim(),
            MaxUploadSizeBytes = 2L * 1024 * 1024 * 1024
        };

        try
        {
            SetConfigEnabled(false);
            AppendLog($"Starting server on port {port}...");

            var contentRoot = AppContext.BaseDirectory;
            _server = ServerBootstrap.CreateServer(settings, contentRoot);

            _logger = _server.Services.GetRequiredService<TransferLogger>();
            _logger.OnNewEntry += OnLogEntry;

            await _server.StartAsync();

            // keep watching for server errors in the background
            _ = Task.Run(async () =>
            {
                try
                {
                    await _server.WaitForShutdownAsync();
                }
                catch (OperationCanceledException) { }
                catch (Exception ex)
                {
                    Dispatcher.Invoke(() =>
                    {
                        AppendLog($"❌ Server error: {ex.Message}");

                        var msg = ex.Message + (ex.InnerException?.Message ?? "");
                        if (msg.Contains("address already in use", StringComparison.OrdinalIgnoreCase)
                            || msg.Contains("access denied", StringComparison.OrdinalIgnoreCase))
                        {
                            AppendLog($"💡 Port {port} may be in use. Try a different port.");
                        }

                        ResetServerState();
                    });
                }
            });

            var ip = _networkService.GetLocalIpAddress();
            var url = $"http://{ip}:{port}";

            // green = running, dark red = stopped
            StatusDot.Fill = new System.Windows.Media.SolidColorBrush(
                System.Windows.Media.Color.FromRgb(0, 128, 0));
            StatusText.Text = "Running";
            UrlText.Text = url;
            IpText.Text = ip;
            StatusBarText.Text = $"Server running on port {port}";

            GenerateQrCode(url);

            AppendLog($"[OK] Server running at {url}");
            AppendLog($"[OK] Shared folder: {Path.GetFullPath(sharedFolder)}");

            if (!string.IsNullOrEmpty(settings.Pin))
                AppendLog("[PIN] PIN protection enabled.");
            else
                AppendLog("[OPEN] No PIN — anyone on the LAN can access files.");
        }
        catch (Exception ex)
        {
            AppendLog($"❌ Failed to start: {ex.Message}");
            ResetServerState();
        }
    }

    private async void StopButton_Click(object sender, RoutedEventArgs e)
    {
        await StopServer();
    }

    private async Task StopServer()
    {
        if (_server == null) return;

        try
        {
            AppendLog("Stopping server...");

            if (_logger != null)
                _logger.OnNewEntry -= OnLogEntry;

            // give it 5 seconds to finish any in-flight requests
            using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(5));
            await _server.StopAsync(cts.Token);

            _server = null;
            _logger = null;

            ResetServerState();
            AppendLog("⏹ Server stopped.");
        }
        catch (Exception ex)
        {
            AppendLog($"Error stopping server: {ex.Message}");
        }
    }

    private void ResetServerState()
    {
        StatusDot.Fill = new System.Windows.Media.SolidColorBrush(
            System.Windows.Media.Color.FromRgb(128, 0, 0));
        StatusText.Text = "Stopped";
        UrlText.Text = "—";
        QrCard.Visibility = Visibility.Collapsed;
        StatusBarText.Text = "Ready";
        SetConfigEnabled(true);
    }

    private void SetConfigEnabled(bool enabled)
    {
        FolderPathBox.IsEnabled = enabled;
        PortBox.IsEnabled = enabled;
        PinBox.IsEnabled = enabled;
        StartButton.IsEnabled = enabled;
        StopButton.IsEnabled = !enabled;
    }

    private void BrowseFolder_Click(object sender, RoutedEventArgs e)
    {
        var dialog = new OpenFolderDialog
        {
            Title = "Select Shared Folder",
            InitialDirectory = FolderPathBox.Text
        };

        if (dialog.ShowDialog() == true)
            FolderPathBox.Text = dialog.FolderName;
    }

    private void UrlText_Click(object sender, System.Windows.Input.MouseButtonEventArgs e)
    {
        var url = UrlText.Text;
        if (url != "—" && url.StartsWith("http"))
        {
            try
            {
                Process.Start(new ProcessStartInfo(url) { UseShellExecute = true });
            }
            catch { }
        }
    }

    private void ClearLogs_Click(object sender, RoutedEventArgs e)
    {
        LogText.Text = "";
        _logger?.Clear();
    }

    private void GenerateQrCode(string url)
    {
        try
        {
            using var qrGenerator = new QRCodeGenerator();
            var qrData = qrGenerator.CreateQrCode(url, QRCodeGenerator.ECCLevel.M);
            using var qrCode = new PngByteQRCode(qrData);
            var qrBytes = qrCode.GetGraphic(8);

            // load the raw PNG bytes into a WPF BitmapImage via MemoryStream
            var image = new BitmapImage();
            using var ms = new MemoryStream(qrBytes);
            image.BeginInit();
            image.CacheOption = BitmapCacheOption.OnLoad;
            image.StreamSource = ms;
            image.EndInit();
            image.Freeze(); // make it thread-safe

            QrImage.Source = image;
            QrUrlText.Text = url;
            QrCard.Visibility = Visibility.Visible;
        }
        catch (Exception ex)
        {
            AppendLog($"QR generation failed: {ex.Message}");
        }
    }

    private void OnLogEntry(LogEntry entry)
    {
        // this fires on a background thread — Dispatcher gets us back to the UI thread
        Dispatcher.Invoke(() => AppendLog(entry.ToString()));
    }

    private void AppendLog(string message)
    {
        var timestamp = DateTime.Now.ToString("HH:mm:ss");
        LogText.Text += $"\n[{timestamp}] {message}";
        LogScrollViewer.ScrollToEnd();
    }

    private void OnWindowStateChanged(object? sender, EventArgs e)
    {
        if (WindowState != WindowState.Minimized) return;

        Hide();

        if (!_hasShownTrayHint)
        {
            _hasShownTrayHint = true;
            AppendLog("💡 Penless is running in the system tray.");
        }
    }

    private async void Window_Closing(object? sender, CancelEventArgs e)
    {
        if (_isClosingForReal)
        {
            if (_server != null)
                await StopServer();
            return;
        }

        // user hit X — don't actually close, just hide to tray
        e.Cancel = true;
        WindowState = WindowState.Minimized;
        Hide();

        if (!_hasShownTrayHint)
        {
            _hasShownTrayHint = true;
            AppendLog("💡 Penless is running in the system tray. Right-click the tray icon to exit.");
        }
    }

    // called by the tray Exit item when the user actually wants to quit
    internal async Task RequestClose()
    {
        _isClosingForReal = true;
        if (_server != null)
            await StopServer();
        Close();
    }
}