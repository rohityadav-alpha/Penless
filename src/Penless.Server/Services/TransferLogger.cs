using System.Collections.Concurrent;

namespace Penless.Server.Services;

// Simple in-memory log buffer. Thread-safe because Kestrel handlers
// can run on multiple threads simultaneously.
public sealed class TransferLogger
{
    private readonly ConcurrentQueue<LogEntry> _entries = new();
    private readonly int _maxEntries;

    public TransferLogger(int maxEntries = 500)
    {
        _maxEntries = maxEntries;
    }

    // the WPF window subscribes to this to update its log panel in real time
    public event Action<LogEntry>? OnNewEntry;

    public void Log(string action, string detail, string? clientIp = null)
    {
        var entry = new LogEntry
        {
            Timestamp = DateTime.Now,
            Action = action,
            Detail = detail,
            ClientIp = clientIp ?? "local"
        };

        _entries.Enqueue(entry);

        // trim from the front once we hit the cap
        while (_entries.Count > _maxEntries)
            _entries.TryDequeue(out _);

        OnNewEntry?.Invoke(entry);
    }

    public IReadOnlyList<LogEntry> GetRecent(int count = 50)
    {
        return _entries.TakeLast(Math.Min(count, _entries.Count)).Reverse().ToList();
    }

    public void Clear() => _entries.Clear();
}

public sealed class LogEntry
{
    public DateTime Timestamp { get; init; }
    public string Action { get; init; } = "";
    public string Detail { get; init; } = "";
    public string ClientIp { get; init; } = "";

    public override string ToString() =>
        $"[{Timestamp:HH:mm:ss}] [{Action}] {Detail} (from {ClientIp})";
}
