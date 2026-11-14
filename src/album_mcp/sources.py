"""Capture sources: macOS Photos library (read-only) and plain image folders.

Folder source covers Android (and anything else): sync the phone's
Screenshots folder to the Mac with Google Drive for desktop, `adb pull`,
or USB, then point ALBUM_MCP_FOLDERS at it.
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
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

    # Reload the library at most this often so a long-running server sees new photos.
    REFRESH_SECONDS = int(os.environ.get("ALBUM_MCP_PHOTOS_REFRESH", "300"))

    def __init__(self, library: str | None = None, screenshots_only: bool = True):
        self.library = library
        self.screenshots_only = screenshots_only
        self._db = None
        self._images_cache = None
        self._loaded_at = 0.0

    def _photosdb(self):
        if self._db is not None and self._loaded_at and time.monotonic() - self._loaded_at > self.REFRESH_SECONDS:
            self._db = None
            self._images_cache = None
        if self._db is None:
            import osxphotos

            lib = self.library or os.path.expanduser("~/Pictures/Photos Library.photoslibrary")
            try:
                self._db = osxphotos.PhotosDB(lib)
                self._loaded_at = time.monotonic()
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

    def _item(self, p) -> Item | None:
        path = self._best_path(p)
        if not path:
            return None
        return Item(
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

    def _images(self) -> list:
        """All still images, read once per process and kept in memory."""
        db = self._photosdb()  # may drop a stale cache
        if self._images_cache is None:
            self._images_cache = db.photos(images=True, movies=False)
        return self._images_cache

    def items(self, since: datetime | None) -> Iterator[Item]:
        for p in self._images():
            if self.screenshots_only and not p.screenshot:
                continue
            if since and _local_naive(p.date) <= since:
                continue
            it = self._item(p)
            if it:
                yield it

    def find(self, labels: list[str], since: datetime | None, until: datetime | None, limit: int) -> list[Item]:
        """Whole library (not only screenshots), filtered by Apple labels and date.
        A photo matches if it has any of `labels` (case-insensitive). Newest first. No OCR."""
        want = {l.strip().lower() for l in labels if l.strip()}
        hits = []
        for p in self._images():
            d = _local_naive(p.date)
            if since and d < since:
                continue
            if until and d > until:
                continue
            if want and not (want & set(p.labels_normalized or [])):
                continue
            hits.append(p)
        hits.sort(key=lambda p: p.date, reverse=True)
        out = []
        for p in hits:
            it = self._item(p)
            if it:
                out.append(it)
            if len(out) >= limit:
                break
        return out

    def get(self, uuid: str) -> Item | None:
        p = self._photosdb().get_photo(uuid)
        return self._item(p) if p else None


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
