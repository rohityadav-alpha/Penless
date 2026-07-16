namespace Penless.Server.Configuration;

// Settings that flow from the WPF UI into the embedded server.
// These get registered with IOptions<PenlessSettings> in ServerBootstrap.
public sealed class PenlessSettings
{
    public const string SectionName = "Penless";

    public string SharedFolder { get; set; } = "SharedFiles";

    public int Port { get; set; } = 8080;

    // empty string = no PIN, anyone on the LAN can connect
    public string Pin { get; set; } = "";

    // 2 GB default — big enough for most files
    public long MaxUploadSizeBytes { get; set; } = 2L * 1024 * 1024 * 1024;

    public int MaxLogEntries { get; set; } = 500;
}
