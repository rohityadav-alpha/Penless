using Microsoft.Extensions.Options;
using Penless.Server.Configuration;
using Penless.Server.Services;

namespace Penless.Server.Endpoints;

public static class FileEndpoints
{
    public static void MapFileEndpoints(this WebApplication app)
    {
        var api = app.MapGroup("/api");

        // list files and folders at a given path (defaults to root)
        api.MapGet("/files", (HttpContext ctx, FileService fileService, string? path) =>
        {
            var result = fileService.Browse(path ?? "");
            if (result.Error != null)
                return Results.NotFound(new { error = result.Error });

            return Results.Ok(result);
        })
        .WithName("BrowseFiles");

        // download a single file — range processing means large files work fine
        api.MapGet("/files/download", (HttpContext ctx, FileService fileService, TransferLogger logger, string path) =>
        {
            if (string.IsNullOrWhiteSpace(path))
                return Results.BadRequest(new { error = "File path is required." });

            var fullPath = fileService.GetFilePath(path);
            if (fullPath == null)
                return Results.NotFound(new { error = "File not found or access denied." });

            var clientIp = ctx.Connection.RemoteIpAddress?.ToString() ?? "unknown";
            var fileName = Path.GetFileName(fullPath);
            logger.Log("DOWNLOAD", $"{fileName} ({FormatSize(new FileInfo(fullPath).Length)})", clientIp);

            return Results.File(fullPath, GetContentType(fileName), fileName, enableRangeProcessing: true);
        })
        .WithName("DownloadFile");

        // upload one or more files via multipart form
        api.MapPost("/upload", async (HttpContext ctx, FileService fileService,
            TransferLogger logger, IOptions<PenlessSettings> settings) =>
        {
            var clientIp = ctx.Connection.RemoteIpAddress?.ToString() ?? "unknown";
            var maxSize = settings.Value.MaxUploadSizeBytes;
            var targetFolder = ctx.Request.Query["folder"].FirstOrDefault() ?? "";

            if (!ctx.Request.HasFormContentType)
                return Results.BadRequest(new { error = "Expected multipart form data." });

            var form = await ctx.Request.ReadFormAsync();
            var results = new List<object>();

            foreach (var file in form.Files)
            {
                if (file.Length <= 0) continue;

                if (file.Length > maxSize)
                {
                    results.Add(new { name = file.FileName, error = $"File exceeds maximum size of {FormatSize(maxSize)}." });
                    continue;
                }

                try
                {
                    using var stream = file.OpenReadStream();
                    var saveResult = await fileService.SaveFileAsync(stream, file.FileName, targetFolder);

                    if (saveResult.Success)
                    {
                        logger.Log("UPLOAD", $"{saveResult.FileName} ({FormatSize(saveResult.Size)})", clientIp);
                        results.Add(new
                        {
                            name = saveResult.FileName,
                            size = saveResult.Size,
                            sizeFormatted = FormatSize(saveResult.Size),
                            path = saveResult.Path
                        });
                    }
                    else
                    {
                        results.Add(new { name = file.FileName, error = saveResult.Error });
                    }
                }
                catch (Exception ex)
                {
                    logger.Log("UPLOAD_ERROR", $"{file.FileName}: {ex.Message}", clientIp);
                    results.Add(new { name = file.FileName, error = "Upload failed. Please try again." });
                }
            }

            return Results.Ok(new { uploaded = results.Count, files = results });
        })
        .DisableAntiforgery()
        .WithName("UploadFiles");

        api.MapPost("/folders", (HttpContext ctx, FileService fileService, TransferLogger logger,
            string? path, string name) =>
        {
            var clientIp = ctx.Connection.RemoteIpAddress?.ToString() ?? "unknown";
            var result = fileService.CreateFolder(path ?? "", name);
            if (result == null)
                return Results.BadRequest(new { error = "Invalid folder name." });

            logger.Log("CREATE_FOLDER", result, clientIp);
            return Results.Ok(new { path = result });
        })
        .WithName("CreateFolder");

        api.MapDelete("/files", (HttpContext ctx, FileService fileService, TransferLogger logger, string path) =>
        {
            var clientIp = ctx.Connection.RemoteIpAddress?.ToString() ?? "unknown";
            if (!fileService.DeleteFile(path))
                return Results.NotFound(new { error = "File not found or access denied." });

            logger.Log("DELETE", path, clientIp);
            return Results.Ok(new { deleted = path });
        })
        .WithName("DeleteFile");

        api.MapDelete("/folders", (HttpContext ctx, FileService fileService, TransferLogger logger, string path) =>
        {
            var clientIp = ctx.Connection.RemoteIpAddress?.ToString() ?? "unknown";
            if (!fileService.DeleteFolder(path))
                return Results.NotFound(new { error = "Folder not found or access denied." });

            logger.Log("DELETE_FOLDER", path, clientIp);
            return Results.Ok(new { deleted = path });
        })
        .WithName("DeleteFolder");

        api.MapPatch("/files", (HttpContext ctx, FileService fileService, TransferLogger logger,
            string path, string newName) =>
        {
            var clientIp = ctx.Connection.RemoteIpAddress?.ToString() ?? "unknown";
            var result = fileService.Rename(path, newName);
            if (result == null)
                return Results.BadRequest(new { error = "Invalid name or path, or destination already exists." });

            logger.Log("RENAME", $"{path} → {result}", clientIp);
            return Results.Ok(new { newPath = result });
        })
        .WithName("RenameItem");
    }

    private static string GetContentType(string fileName)
    {
        var ext = Path.GetExtension(fileName).ToLowerInvariant();
        return ext switch
        {
            ".pdf" => "application/pdf",
            ".zip" => "application/zip",
            ".rar" => "application/x-rar-compressed",
            ".7z" => "application/x-7z-compressed",
            ".tar" => "application/x-tar",
            ".gz" => "application/gzip",
            ".jpg" or ".jpeg" => "image/jpeg",
            ".png" => "image/png",
            ".gif" => "image/gif",
            ".svg" => "image/svg+xml",
            ".webp" => "image/webp",
            ".mp4" => "video/mp4",
            ".mp3" => "audio/mpeg",
            ".wav" => "audio/wav",
            ".txt" => "text/plain",
            ".csv" => "text/csv",
            ".json" => "application/json",
            ".xml" => "application/xml",
            ".html" or ".htm" => "text/html",
            ".css" => "text/css",
            ".js" => "application/javascript",
            ".doc" => "application/msword",
            ".docx" => "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".xls" => "application/vnd.ms-excel",
            ".xlsx" => "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".ppt" => "application/vnd.ms-powerpoint",
            ".pptx" => "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ".exe" => "application/x-msdownload",
            ".iso" => "application/x-iso9660-image",
            _ => "application/octet-stream"
        };
    }

    public static string FormatSize(long bytes)
    {
        string[] sizes = ["B", "KB", "MB", "GB", "TB"];
        double len = bytes;
        var order = 0;
        while (len >= 1024 && order < sizes.Length - 1)
        {
            order++;
            len /= 1024;
        }
        return $"{len:0.##} {sizes[order]}";
    }
}
