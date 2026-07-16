using Penless.Server.Configuration;
using Penless.Server.Services;
using Microsoft.Extensions.Options;

namespace Penless.Server.Middleware;

// Handles PIN auth and logs every API request.
// Sits right after CORS in the pipeline so it runs before any endpoint logic.
public sealed class SecurityMiddleware
{
    private readonly RequestDelegate _next;
    private readonly PenlessSettings _settings;
    private readonly TransferLogger _logger;

    // these two paths are always public — you need them to even log in
    private static readonly string[] PublicPaths = ["/api/auth", "/api/status"];

    public SecurityMiddleware(RequestDelegate next, IOptions<PenlessSettings> settings, TransferLogger logger)
    {
        _next = next;
        _settings = settings.Value;
        _logger = logger;
    }

    public async Task InvokeAsync(HttpContext context)
    {
        var path = context.Request.Path.Value ?? "";
        var clientIp = context.Connection.RemoteIpAddress?.ToString() ?? "unknown";

        if (path.StartsWith("/api/"))
            _logger.Log("REQUEST", $"{context.Request.Method} {path}", clientIp);

        if (!string.IsNullOrEmpty(_settings.Pin) && path.StartsWith("/api/"))
        {
            var isPublic = PublicPaths.Any(p => path.StartsWith(p, StringComparison.OrdinalIgnoreCase));
            if (!isPublic)
            {
                // accept PIN from either a header (desktop clients) or query string (browser links)
                var authHeader = context.Request.Headers["X-Pin"].FirstOrDefault();
                var queryPin = context.Request.Query["pin"].FirstOrDefault();
                var pin = authHeader ?? queryPin;

                if (pin != _settings.Pin)
                {
                    _logger.Log("AUTH_FAIL", $"Invalid PIN for {path}", clientIp);
                    context.Response.StatusCode = 401;
                    await context.Response.WriteAsJsonAsync(new
                    {
                        error = "Invalid PIN. Please enter the correct PIN to access files."
                    });
                    return;
                }
            }
        }

        await _next(context);
    }
}
