using System.Text.RegularExpressions;

namespace Penless.Server.Services;

// All file system operations go through here.
// The key design goal is that nothing outside this class touches the disk directly —
// everything gets validated first so there's no way to escape the shared folder.
public sealed partial class FileService
{
    private readonly string _rootPath;

    public FileService(string sharedFolderPath)
    {
        _rootPath = Path.GetFullPath(sharedFolderPath);
        Directory.CreateDirectory(_rootPath);
    }

    public string RootPath => _rootPath;

    public BrowseResult Browse(string relativePath = "")
    {
        var fullPath = ResolveSafePath(relativePath);
        if (fullPath == null || !Directory.Exists(fullPath))
            return new BrowseResult { Error = "Directory not found." };

        var dirInfo = new DirectoryInfo(fullPath);
        var currentRelative = Path.GetRelativePath(_rootPath, fullPath).Replace('\\', '/');
        if (currentRelative == ".") currentRelative = "";

        var folders = dirInfo.GetDirectories()
            .Where(d => !d.Attributes.HasFlag(FileAttributes.Hidden))
            .Select(d => new FolderItem
            {
                Name = d.Name,
                Path = CombineRelative(currentRelative, d.Name),
                ItemCount = d.GetFileSystemInfos().Length,
                Modified = d.LastWriteTime
            })
            .OrderBy(f => f.Name)
            .ToList();

        var files = dirInfo.GetFiles()
            .Where(f => !f.Attributes.HasFlag(FileAttributes.Hidden))
            .Select(f => new FileItem
            {
                Name = f.Name,
                Path = CombineRelative(currentRelative, f.Name),
                Size = f.Length,
                Modified = f.LastWriteTime,
                Extension = f.Extension.TrimStart('.').ToLowerInvariant()
            })
            .OrderBy(f => f.Name)
            .ToList();

        return new BrowseResult
        {
            CurrentPath = currentRelative,
            ParentPath = string.IsNullOrEmpty(currentRelative) ? null
                : Path.GetDirectoryName(currentRelative)?.Replace('\\', '/') ?? "",
            Folders = folders,
            Files = files
        };
    }

    public string? GetFilePath(string relativePath)
    {
        var fullPath = ResolveSafePath(relativePath);
        if (fullPath == null || !File.Exists(fullPath)) return null;
        return fullPath;
    }

    public async Task<SaveResult> SaveFileAsync(Stream fileStream, string fileName,
        string targetFolder = "", CancellationToken ct = default)
    {
        var sanitized = SanitizeFileName(fileName);
        if (string.IsNullOrWhiteSpace(sanitized))
            return new SaveResult { Error = "Invalid file name." };

        var folderPath = ResolveSafePath(targetFolder) ?? _rootPath;
        if (!Directory.Exists(folderPath))
            Directory.CreateDirectory(folderPath);

        var filePath = Path.Combine(folderPath, sanitized);
        filePath = GetUniqueFilePath(filePath); // avoid stomping existing files

        await using var fs = new FileStream(filePath, FileMode.Create, FileAccess.Write,
            FileShare.None, bufferSize: 81920, useAsync: true);
        await fileStream.CopyToAsync(fs, 81920, ct);

        var info = new FileInfo(filePath);
        return new SaveResult
        {
            FileName = info.Name,
            Size = info.Length,
            Path = Path.GetRelativePath(_rootPath, filePath).Replace('\\', '/')
        };
    }

    public string? CreateFolder(string relativePath, string folderName)
    {
        var sanitized = SanitizeFileName(folderName);
        if (string.IsNullOrWhiteSpace(sanitized)) return null;

        var parentPath = ResolveSafePath(relativePath) ?? _rootPath;
        var newPath = Path.Combine(parentPath, sanitized);

        var full = Path.GetFullPath(newPath);
        if (!full.StartsWith(_rootPath, StringComparison.OrdinalIgnoreCase)) return null;

        Directory.CreateDirectory(full);
        return Path.GetRelativePath(_rootPath, full).Replace('\\', '/');
    }

    public bool DeleteFile(string relativePath)
    {
        var fullPath = ResolveSafePath(relativePath);
        if (fullPath == null || !File.Exists(fullPath)) return false;

        File.Delete(fullPath);
        return true;
    }

    public bool DeleteFolder(string relativePath)
    {
        // refuse to nuke the whole shared root
        if (string.IsNullOrWhiteSpace(relativePath)) return false;

        var fullPath = ResolveSafePath(relativePath);
        if (fullPath == null || !Directory.Exists(fullPath)) return false;

        if (string.Equals(fullPath, _rootPath, StringComparison.OrdinalIgnoreCase)) return false;

        Directory.Delete(fullPath, recursive: true);
        return true;
    }

    public string? Rename(string relativePath, string newName)
    {
        var sanitized = SanitizeFileName(newName);
        if (string.IsNullOrWhiteSpace(sanitized)) return null;

        var sourcePath = ResolveSafePath(relativePath);
        if (sourcePath == null) return null;

        if (!File.Exists(sourcePath) && !Directory.Exists(sourcePath)) return null;

        var parentDir = Path.GetDirectoryName(sourcePath)!;
        var destPath = Path.GetFullPath(Path.Combine(parentDir, sanitized));

        if (!destPath.StartsWith(_rootPath, StringComparison.OrdinalIgnoreCase)) return null;
        if (File.Exists(destPath) || Directory.Exists(destPath)) return null; // no overwrite

        if (File.Exists(sourcePath))
            File.Move(sourcePath, destPath);
        else
            Directory.Move(sourcePath, destPath);

        return Path.GetRelativePath(_rootPath, destPath).Replace('\\', '/');
    }

    // Resolves a relative path and makes sure it stays inside the shared root.
    // Returns null if something looks fishy.
    private string? ResolveSafePath(string relativePath)
    {
        if (string.IsNullOrWhiteSpace(relativePath))
            return _rootPath;

        if (relativePath.Contains("..") || relativePath.Contains('\0'))
            return null;

        var combined = Path.Combine(_rootPath, relativePath.Replace('/', '\\'));
        var full = Path.GetFullPath(combined);

        return full.StartsWith(_rootPath, StringComparison.OrdinalIgnoreCase) ? full : null;
    }

    private static string SanitizeFileName(string name)
    {
        name = name.Replace('/', '_').Replace('\\', '_').Replace('\0', '_');

        foreach (var c in Path.GetInvalidFileNameChars())
            name = name.Replace(c, '_');

        name = name.Trim('.', ' ');
        name = MultiUnderscoreRegex().Replace(name, "_");

        return name.Length > 255 ? name[..255] : name;
    }

    private static string GetUniqueFilePath(string filePath)
    {
        if (!File.Exists(filePath)) return filePath;

        var dir = Path.GetDirectoryName(filePath)!;
        var name = Path.GetFileNameWithoutExtension(filePath);
        var ext = Path.GetExtension(filePath);
        var counter = 1;

        string newPath;
        do
        {
            newPath = Path.Combine(dir, $"{name} ({counter}){ext}");
            counter++;
        } while (File.Exists(newPath));

        return newPath;
    }

    private static string CombineRelative(string basePath, string name)
        => string.IsNullOrEmpty(basePath) ? name : $"{basePath}/{name}";

    [GeneratedRegex(@"_{2,}")]
    private static partial Regex MultiUnderscoreRegex();
}

// result types — kept simple, just data bags
public sealed class BrowseResult
{
    public string CurrentPath { get; init; } = "";
    public string? ParentPath { get; init; }
    public List<FolderItem> Folders { get; init; } = [];
    public List<FileItem> Files { get; init; } = [];
    public string? Error { get; init; }
}

public sealed class FolderItem
{
    public string Name { get; init; } = "";
    public string Path { get; init; } = "";
    public int ItemCount { get; init; }
    public DateTime Modified { get; init; }
}

public sealed class FileItem
{
    public string Name { get; init; } = "";
    public string Path { get; init; } = "";
    public long Size { get; init; }
    public DateTime Modified { get; init; }
    public string Extension { get; init; } = "";
}

public sealed class SaveResult
{
    public string? FileName { get; init; }
    public long Size { get; init; }
    public string? Path { get; init; }
    public string? Error { get; init; }
    public bool Success => Error == null;
}
