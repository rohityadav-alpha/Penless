using Microsoft.Extensions.Options;
using Penless.Server.Configuration;
using Penless.Server.Services;
using QRCoder;

namespace Penless.Server.Endpoints;

public static class StatusEndpoints
{
    public static void MapStatusEndpoints(this WebApplication app)
    {
        var api = app.MapGroup("/api");

        api.MapGet("/status", (NetworkService networkService, IOptions<PenlessSettings> settings) =>
        {
            var ip = networkService.GetLocalIpAddress();
            var port = settings.Value.Port;

            return Results.Ok(new
            {
                status = "running",
                localIp = ip,
                port,
                url = $"http://{ip}:{port}",
                sharedFolder = Path.GetFullPath(settings.Value.SharedFolder),
                pinRequired = !string.IsNullOrEmpty(settings.Value.Pin),
                maxUploadSize = settings.Value.MaxUploadSizeBytes,
                maxUploadSizeFormatted = FileEndpoints.FormatSize(settings.Value.MaxUploadSizeBytes),
                networkAvailable = networkService.IsNetworkAvailable()
            });
        })
        .WithName("GetStatus");

        api.MapPost("/auth", async (HttpContext ctx, IOptions<PenlessSettings> settings) =>
        {
            var pin = settings.Value.Pin;
            if (string.IsNullOrEmpty(pin))
                return Results.Ok(new { authenticated = true, message = "No PIN required." });

            var body = await ctx.Request.ReadFromJsonAsync<PinRequest>();
            if (body?.Pin == pin)
                return Results.Ok(new { authenticated = true });

            return Results.Json(new { authenticated = false, error = "Incorrect PIN." }, statusCode: 401);
        })
        .WithName("Authenticate");

        // returns a raw PNG — the browser renders it directly in an <img> tag
        api.MapGet("/qrcode", (NetworkService networkService, IOptions<PenlessSettings> settings) =>
        {
            var ip = networkService.GetLocalIpAddress();
            var url = $"http://{ip}:{settings.Value.Port}";

            using var qrGenerator = new QRCodeGenerator();
            var qrData = qrGenerator.CreateQrCode(url, QRCodeGenerator.ECCLevel.M);
            using var qrCode = new PngByteQRCode(qrData);
            var qrBytes = qrCode.GetGraphic(8);

            return Results.File(qrBytes, "image/png", "penless-qr.png");
        })
        .WithName("GetQRCode");

        api.MapGet("/logs", (TransferLogger logger, int? count) =>
        {
            var entries = logger.GetRecent(count ?? 50);
            return Results.Ok(new
            {
                entries = entries.Select(e => new
                {
                    timestamp = e.Timestamp.ToString("yyyy-MM-dd HH:mm:ss"),
                    action = e.Action,
                    detail = e.Detail,
                    clientIp = e.ClientIp
                })
            });
        })
        .WithName("GetLogs");
    }
}

internal sealed class PinRequest
{
    public string Pin { get; set; } = "";
}
