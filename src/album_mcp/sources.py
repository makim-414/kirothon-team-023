"""Capture sources: macOS Photos library (read-only) and plain image folders.

Folder source covers Android (and anything else): sync the phone's
Screenshots folder to the Mac with Google Drive for desktop, `adb pull`,
or USB, then point ALBUM_MCP_FOLDERS at it.
"""

from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator, Protocol

log = logging.getLogger(__name__)

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".heic", ".webp"}

FDA_HELP = (
    "macOS blocked access to the Photos library. Grant Full Disk Access to the app that "
    "runs this server (Kiro, Terminal, or iTerm): System Settings > Privacy & Security > "
    "Full Disk Access, then restart it. The folder source keeps working meanwhile."
)


class SourceUnavailable(RuntimeError):
    pass


@dataclass
class Item:
    id: str
    source: str
    path: str
    filename: str
    created_at: datetime  # naive local time
    width: int | None = None
    height: int | None = None
    size_bytes: int | None = None
    labels: list[str] | None = None

    def as_row(self, ocr_text: str) -> dict:
        return {
            "id": self.id,
            "source": self.source,
            "path": self.path,
            "filename": self.filename,
            "created_at": self.created_at.isoformat(timespec="seconds"),
            "width": self.width,
            "height": self.height,
            "size_bytes": self.size_bytes,
            "ocr_text": ocr_text,
            "labels": self.labels or [],
        }


class Source(Protocol):
    name: str

    def items(self, since: datetime | None) -> Iterator[Item]: ...


def _local_naive(dt: datetime) -> datetime:
    return dt.astimezone().replace(tzinfo=None) if dt.tzinfo else dt


class PhotosSource:
    """macOS Photos via osxphotos. osxphotos reads a copy of Photos.sqlite, so the
    library itself is never written to."""

    name = "photos"

    def __init__(self, library: str | None = None, screenshots_only: bool = True):
        self.library = library
        self.screenshots_only = screenshots_only
        self._db = None

    def _photosdb(self):
        if self._db is None:
            import osxphotos

            lib = self.library or os.path.expanduser("~/Pictures/Photos Library.photoslibrary")
            try:
                self._db = osxphotos.PhotosDB(lib)
            except (OSError, FileNotFoundError, PermissionError) as e:
                raise SourceUnavailable(FDA_HELP) from e
        return self._db

    @staticmethod
    def _best_path(p) -> str | None:
        if p.path and not p.ismissing:
            return p.path
        # Original only in iCloud: use the largest local preview (Req 1.4 / 9.3).
        for d in p.path_derivatives or []:
            if os.path.exists(d):
                return d
        return None

    def items(self, since: datetime | None) -> Iterator[Item]:
        db = self._photosdb()
        kw = {"from_date": since.astimezone()} if since else {}
        photos = db.photos(images=True, movies=False, **kw)
        for p in photos:
            if self.screenshots_only and not p.screenshot:
                continue
            path = self._best_path(p)
            if not path:
                continue
            yield Item(
                id=f"photos:{p.uuid}",
                source=self.name,
                path=path,
                filename=p.original_filename or Path(path).name,
                created_at=_local_naive(p.date),
                width=p.width,
                height=p.height,
                size_bytes=p.original_filesize,
                labels=list(p.labels or []),
            )


class FolderSource:
    name = "folder"

    def __init__(self, folders: list[str]):
        self.folders = [Path(f).expanduser() for f in folders if f]

    def items(self, since: datetime | None) -> Iterator[Item]:
        cutoff = since.timestamp() if since else 0
        for root in self.folders:
            if not root.is_dir():
                log.warning("folder source missing: %s", root)
                continue
            for dirpath, _, files in os.walk(root):
                for f in files:
                    p = Path(dirpath) / f
                    if p.suffix.lower() not in IMAGE_EXTS or f.startswith("."):
                        continue
                    st = p.stat()
                    if st.st_mtime <= cutoff:
                        continue
                    yield Item(
                        id="folder:" + hashlib.sha1(str(p.resolve()).encode()).hexdigest()[:16],
                        source=self.name,
                        path=str(p),
                        filename=f,
                        created_at=datetime.fromtimestamp(st.st_mtime),
                        size_bytes=st.st_size,
                        labels=[],
                    )
