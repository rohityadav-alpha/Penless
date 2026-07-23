"""
All file system operations — browse, upload, download, rename, delete.

Every path gets validated to stay inside the shared folder root,
so there's no way to escape via ../ or symlinks.
"""

import os
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from typing import IO, List, Optional


# -- data classes for return values --

@dataclass
class FolderItem:
    name: str
    path: str
    item_count: int
    modified: datetime

    def to_dict(self):
        return {
            "name": self.name,
            "path": self.path,
            "itemCount": self.item_count,
            "modified": self.modified.isoformat(),
        }


@dataclass
class FileItem:
    name: str
    path: str
    size: int
    modified: datetime
    extension: str

    def to_dict(self):
        return {
            "name": self.name,
            "path": self.path,
            "size": self.size,
            "modified": self.modified.isoformat(),
            "extension": self.extension,
        }


@dataclass
class BrowseResult:
    current_path: str = ""
    parent_path: Optional[str] = None
    folders: List[FolderItem] = field(default_factory=list)
    files: List[FileItem] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self):
        return {
            "currentPath": self.current_path,
            "parentPath": self.parent_path,
            "folders": [f.to_dict() for f in self.folders],
            "files": [f.to_dict() for f in self.files],
            "error": self.error,
        }


@dataclass
class SaveResult:
    file_name: Optional[str] = None
    size: int = 0
    path: Optional[str] = None
    error: Optional[str] = None

    @property
    def success(self):
        return self.error is None


# collapses runs of underscores when sanitizing filenames
_MULTI_UNDERSCORE = re.compile(r"_{2,}")


class FileService:
    """
    Handles everything that touches the filesystem.
    Nothing else in the app reads/writes files directly — it all goes through here.
    """

    def __init__(self, shared_folder_path):
        self._root_path = os.path.realpath(shared_folder_path)
        os.makedirs(self._root_path, exist_ok=True)

    @property
    def root_path(self):
        return self._root_path

    def browse(self, relative_path=""):
        """List contents of a directory inside the shared folder."""
        full_path = self._resolve_safe_path(relative_path)
        if full_path is None or not os.path.isdir(full_path):
            return BrowseResult(error="Directory not found.")

        current_relative = os.path.relpath(full_path, self._root_path).replace("\\", "/")
        if current_relative == ".":
            current_relative = ""

        if current_relative:
            parent_path = os.path.dirname(current_relative).replace("\\", "/")
        else:
            parent_path = None

        folders = []
        files = []

        try:
            entries = os.scandir(full_path)
        except PermissionError:
            return BrowseResult(error="Permission denied.")

        with entries:
            for entry in entries:
                if entry.name.startswith("."):
                    continue
                try:
                    stat = entry.stat()
                except OSError:
                    continue

                item_relative = self._combine_relative(current_relative, entry.name)
                modified = datetime.fromtimestamp(stat.st_mtime)

                if entry.is_dir(follow_symlinks=False):
                    try:
                        item_count = len(os.listdir(entry.path))
                    except OSError:
                        item_count = 0
                    folders.append(FolderItem(
                        name=entry.name, path=item_relative,
                        item_count=item_count, modified=modified,
                    ))
                elif entry.is_file(follow_symlinks=False):
                    ext = os.path.splitext(entry.name)[1].lstrip(".").lower()
                    files.append(FileItem(
                        name=entry.name, path=item_relative,
                        size=stat.st_size, modified=modified, extension=ext,
                    ))

        folders.sort(key=lambda f: f.name.lower())
        files.sort(key=lambda f: f.name.lower())

        return BrowseResult(
            current_path=current_relative,
            parent_path=parent_path,
            folders=folders,
            files=files,
        )

    def get_file_path(self, relative_path):
        """Get the full path for a file, or None if it's outside the boundary or doesn't exist."""
        full_path = self._resolve_safe_path(relative_path)
        if full_path is None or not os.path.isfile(full_path):
            return None
        return full_path

    def save_file(self, file_stream, file_name, target_folder=""):
        """Save an uploaded file. Returns a SaveResult with the final name and size."""
        sanitized = self._sanitize_filename(file_name)
        if not sanitized:
            return SaveResult(error="Invalid file name.")

        folder_path = self._resolve_safe_path(target_folder)
        if folder_path is None:
            folder_path = self._root_path
        os.makedirs(folder_path, exist_ok=True)

        dest_path = os.path.join(folder_path, sanitized)
        dest_path = self._get_unique_file_path(dest_path)

        try:
            with open(dest_path, "wb") as out_f:
                shutil.copyfileobj(file_stream, out_f, length=81920)
        except OSError as exc:
            return SaveResult(error=str(exc))

        size = os.path.getsize(dest_path)
        rel = os.path.relpath(dest_path, self._root_path).replace("\\", "/")
        return SaveResult(file_name=os.path.basename(dest_path), size=size, path=rel)

    def create_folder(self, relative_path, folder_name):
        """Create a subdirectory. Returns its relative path, or None on failure."""
        sanitized = self._sanitize_filename(folder_name)
        if not sanitized:
            return None

        parent_path = self._resolve_safe_path(relative_path)
        if parent_path is None:
            parent_path = self._root_path

        new_path = os.path.realpath(os.path.join(parent_path, sanitized))

        if not self._is_within_root(new_path):
            return None

        os.makedirs(new_path, exist_ok=True)
        return os.path.relpath(new_path, self._root_path).replace("\\", "/")

    def delete_file(self, relative_path):
        full_path = self._resolve_safe_path(relative_path)
        if full_path is None or not os.path.isfile(full_path):
            return False
        try:
            os.remove(full_path)
            return True
        except OSError:
            return False

    def delete_folder(self, relative_path):
        """Delete a folder recursively. Won't delete the root shared folder."""
        if not relative_path or relative_path.strip() in ("", "."):
            return False

        full_path = self._resolve_safe_path(relative_path)
        if full_path is None or not os.path.isdir(full_path):
            return False

        # safety: never delete the root itself
        if os.path.normcase(full_path) == os.path.normcase(self._root_path):
            return False

        try:
            shutil.rmtree(full_path)
            return True
        except OSError:
            return False

    def rename(self, relative_path, new_name):
        """Rename a file or folder. Returns the new relative path, or None."""
        sanitized = self._sanitize_filename(new_name)
        if not sanitized:
            return None

        source_path = self._resolve_safe_path(relative_path)
        if source_path is None or not os.path.exists(source_path):
            return None

        parent_dir = os.path.dirname(source_path)
        dest_path = os.path.realpath(os.path.join(parent_dir, sanitized))

        if not self._is_within_root(dest_path):
            return None
        if os.path.exists(dest_path):
            return None  # don't overwrite

        try:
            os.rename(source_path, dest_path)
        except OSError:
            return None

        return os.path.relpath(dest_path, self._root_path).replace("\\", "/")

    # -- internal helpers --

    def _resolve_safe_path(self, relative_path):
        """
        Turn a relative path into an absolute one, making sure it stays
        inside the shared folder. Returns None if anything looks sketchy.
        """
        if not relative_path or relative_path.strip() == "":
            return self._root_path

        # reject obvious traversal attempts
        if ".." in relative_path or "\x00" in relative_path:
            return None

        combined = os.path.join(self._root_path, relative_path.replace("/", os.sep))
        full = os.path.realpath(combined)

        return full if self._is_within_root(full) else None

    def _is_within_root(self, full_path):
        """Check that a path is inside (or equal to) the shared root."""
        norm_root = os.path.normcase(self._root_path)
        norm_path = os.path.normcase(full_path)
        return norm_path == norm_root or norm_path.startswith(norm_root + os.sep)

    @staticmethod
    def _sanitize_filename(name):
        """Strip dangerous chars, collapse underscores, cap at 255 chars."""
        if not name:
            return ""

        name = name.replace("/", "_").replace("\\", "_").replace("\x00", "_")

        invalid_chars = set('<>:"/\\|?*') | {chr(c) for c in range(32)}
        name = "".join("_" if c in invalid_chars else c for c in name)

        name = name.strip(". ")
        name = _MULTI_UNDERSCORE.sub("_", name)

        return name[:255] if len(name) > 255 else name

    @staticmethod
    def _get_unique_file_path(file_path):
        """If the file already exists, append (1), (2), ... until we find a free name."""
        if not os.path.exists(file_path):
            return file_path

        base, ext = os.path.splitext(file_path)
        counter = 1
        while True:
            candidate = f"{base} ({counter}){ext}"
            if not os.path.exists(candidate):
                return candidate
            counter += 1

    @staticmethod
    def _combine_relative(base_path, name):
        return name if not base_path else f"{base_path}/{name}"
