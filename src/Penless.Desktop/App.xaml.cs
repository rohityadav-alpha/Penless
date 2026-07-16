using System.Windows;
using System.Drawing;
using System.Windows.Forms;
using Application = System.Windows.Application;

namespace Penless.Desktop;

// This is the app entry point. Nothing too fancy here —
// mainly just wires up the tray icon and handles the shutdown sequence.
public partial class App : Application
{
    private NotifyIcon? _trayIcon;

    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);
        InitializeTrayIcon();
    }

    private void InitializeTrayIcon()
    {
        _trayIcon = new NotifyIcon
        {
            Text = "Penless — Local File Transfer",
            Visible = true,
            Icon = SystemIcons.Application
        };

        var contextMenu = new ContextMenuStrip();

        // Bold font on the first item is a standard Windows tray convention
        var openItem = new ToolStripMenuItem("Open Penless");
        openItem.Font = new Font(openItem.Font, System.Drawing.FontStyle.Bold);
        openItem.Click += (_, _) => ShowMainWindow();

        var separatorItem = new ToolStripSeparator();

        var exitItem = new ToolStripMenuItem("Exit");
        exitItem.Click += (_, _) => ExitApplication();

        contextMenu.Items.Add(openItem);
        contextMenu.Items.Add(separatorItem);
        contextMenu.Items.Add(exitItem);

        _trayIcon.ContextMenuStrip = contextMenu;
        _trayIcon.DoubleClick += (_, _) => ShowMainWindow();
    }

    private void ShowMainWindow()
    {
        if (MainWindow == null) return;

        MainWindow.Show();
        MainWindow.WindowState = WindowState.Normal;
        MainWindow.Activate();
        MainWindow.Focus();
    }

    private void ExitApplication()
    {
        _trayIcon?.Dispose();
        _trayIcon = null;

        if (MainWindow is MainWindow mainWin)
        {
            // fire-and-forget is fine here, RequestClose is pretty quick
            _ = mainWin.RequestClose();
        }
        else
        {
            Shutdown();
        }
    }

    protected override void OnExit(ExitEventArgs e)
    {
        _trayIcon?.Dispose();
        base.OnExit(e);
    }
}
