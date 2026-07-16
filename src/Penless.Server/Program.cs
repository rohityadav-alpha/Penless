using Microsoft.AspNetCore.Http.Features;
using Microsoft.AspNetCore.Server.Kestrel.Core;
using Penless.Server.Configuration;
using Penless.Server.Endpoints;
using Penless.Server.Middleware;
using Penless.Server.Services;

namespace Penless.Server;

// Builds and configures the embedded ASP.NET Core server.
// Designed to be hosted inside the WPF shell — the caller owns start/stop.
public static class ServerBootstrap
{
    // Creates the WebApplication but doesn't start it.
    // The WPF side calls StartAsync() when the user hits "Start Server".
    public static WebApplication CreateServer(PenlessSettings settings, string? contentRoot = null)
    {
        var builder = WebApplication.CreateBuilder(new WebApplicationOptions
        {
            ContentRootPath = contentRoot ?? AppContext.BaseDirectory,
            WebRootPath = Path.Combine(contentRoot ?? AppContext.BaseDirectory, "wwwroot")
        });

        // wire up settings so endpoints can read them via IOptions<PenlessSettings>
        builder.Services.Configure<PenlessSettings>(opts =>
        {
            opts.SharedFolder = settings.SharedFolder;
            opts.Port = settings.Port;
            opts.Pin = settings.Pin;
            opts.MaxUploadSizeBytes = settings.MaxUploadSizeBytes;
            opts.MaxLogEntries = settings.MaxLogEntries;
        });

        // Kestrel binds on all interfaces so other devices on the LAN can reach it
        builder.WebHost.ConfigureKestrel(options =>
        {
            options.ListenAnyIP(settings.Port);
            options.Limits.MaxRequestBodySize = settings.MaxUploadSizeBytes;
            options.Limits.RequestHeadersTimeout = TimeSpan.FromMinutes(5);
            options.Limits.KeepAliveTimeout = TimeSpan.FromMinutes(10);
        });

        // resolve shared folder path — support both absolute and relative
        var sharedPath = Path.IsPathRooted(settings.SharedFolder)
            ? settings.SharedFolder
            : Path.Combine(AppContext.BaseDirectory, settings.SharedFolder);

        builder.Services.AddSingleton(new FileService(sharedPath));
        builder.Services.AddSingleton(new TransferLogger(settings.MaxLogEntries));
        builder.Services.AddSingleton<NetworkService>();

        // without this, ASP.NET Core caps multipart at 128 MB regardless of Kestrel limit
        builder.Services.Configure<FormOptions>(options =>
            options.MultipartBodyLengthLimit = settings.MaxUploadSizeBytes);

        // CORS wide open — this is a LAN-only tool, not exposed to the internet
        builder.Services.AddCors(options =>
            options.AddDefaultPolicy(policy =>
                policy.AllowAnyOrigin().AllowAnyMethod().AllowAnyHeader()));

        builder.Logging.SetMinimumLevel(LogLevel.Warning);

        var app = builder.Build();

        app.UseCors();
        app.UseMiddleware<SecurityMiddleware>();
        app.UseDefaultFiles();
        app.UseStaticFiles();

        app.MapFileEndpoints();
        app.MapStatusEndpoints();

        // catch-all so refreshing any sub-path in the browser still works
        app.MapFallbackToFile("index.html");

        return app;
    }
}
