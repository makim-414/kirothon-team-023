"""Album service: wires config, sources, DB, OCR and calendars together.

All tool logic lives here so the MCP server, the CLI and tests share it.
"""

from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from . import calendars, preview, search
from .db import DB, Capture
from .ocr import ocr_image
from .sources import FolderSource, PhotosSource, SourceUnavailable

log = logging.getLogger(__name__)

HOME = Path("~/.album-mcp").expanduser()


@dataclass
class Config:
    sources: list[str] = field(default_factory=lambda: ["photos"])
    folders: list[str] = field(default_factory=list)
    photos_library: str | None = None
    db_path: Path = HOME / "album.db"
    calendar: str = "apple"
    calendar_name: str = "Rollcall"
    google_calendar_id: str = "primary"
    ics_dir: Path = HOME / "events"
    ics_open: bool = True

    @classmethod
    def from_env(cls) -> "Config":
        e = os.environ.get
        folders = [f for f in e("ALBUM_MCP_FOLDERS", "").split(":") if f]
        default_sources = "photos,folder" if folders else "photos"
        return cls(
            sources=[s.strip() for s in e("ALBUM_MCP_SOURCES", default_sources).split(",") if s.strip()],
            folders=folders,
            photos_library=e("ALBUM_MCP_PHOTOS_LIBRARY") or None,
            db_path=Path(e("ALBUM_MCP_DB", str(HOME / "album.db"))).expanduser(),
            calendar=e("ALBUM_MCP_CALENDAR", "apple"),
            calendar_name=e("ALBUM_MCP_CALENDAR_NAME", "Rollcall"),
            google_calendar_id=e("ALBUM_MCP_GOOGLE_CALENDAR_ID", "primary"),
            ics_dir=Path(e("ALBUM_MCP_ICS_DIR", str(HOME / "events"))).expanduser(),
            ics_open=e("ALBUM_MCP_ICS_OPEN", "1") == "1",
        )


class Album:
    def __init__(self, cfg: Config | None = None):
        self.cfg = cfg or Config.from_env()
        self.db = DB(self.cfg.db_path)
        self.sources = []
        for s in self.cfg.sources:
            if s == "photos":
                self.sources.append(PhotosSource(self.cfg.photos_library))
            elif s == "folder":
                self.sources.append(FolderSource(self.cfg.folders))
            else:
                raise ValueError(f"unknown source {s!r} (use photos, folder)")
        self._calendar = None
        self._photos = next((s for s in self.sources if isinstance(s, PhotosSource)), None)

    def photos_source(self) -> PhotosSource:
        # find_photos works even if the photos source is not used for sync
        if self._photos is None:
            self._photos = PhotosSource(self.cfg.photos_library)
        return self._photos

    @property
    def calendar(self):
        if self._calendar is None:
            c = self.cfg
            self._calendar = calendars.make_backend(
                c.calendar,
                calendar_name=c.calendar_name,
                google_calendar_id=c.google_calendar_id,
                ics_dir=c.ics_dir,
                ics_open=c.ics_open,
            )
        return self._calendar

    # ---- sync -----------------------------------------------------------
    def sync(self, since: str | None = None, limit: int = 30, days: int = 30) -> dict:
        """Index captures from the last `days` days (or since `since`), newest first.

        Runs OCR on at most `limit` not-yet-indexed captures per call; call again
        while `remaining` > 0. Already-indexed captures are skipped, so repeated
        calls walk backwards through the window.
        """
        since_dt = datetime.fromisoformat(since) if since else datetime.now() - timedelta(days=days)
        if since_dt.tzinfo:
            since_dt = since_dt.astimezone().replace(tzinfo=None)

        errors, pending = [], []
        for src in self.sources:
            try:
                pending += [it for it in src.items(since_dt) if not self.db.has(it.id)]
            except SourceUnavailable as e:
                errors.append({"source": src.name, "error": str(e)})
        pending.sort(key=lambda it: it.created_at, reverse=True)

        added = []
        for it in pending[:limit]:
            text = ocr_image(it.path)
            row = it.as_row(text)
            if it.width is None:
                try:
                    from PIL import Image

                    with Image.open(it.path) as im:
                        row["width"], row["height"] = im.size
                except Exception:
                    pass
            self.db.upsert_capture(row)
            added.append({"id": it.id, "created_at": row["created_at"], "path": it.path})

        remaining = len(pending) - len(added)
        self.db.set_state("last_sync", datetime.now().isoformat(timespec="seconds"))
        return {
            "added": added,
            "remaining": remaining,
            "unfiled_total": self.db.count_unfiled(),
            "window_since": since_dt.isoformat(timespec="seconds"),
            "errors": errors,
        }

    # ---- queue / classification -----------------------------------------
    def inbox(self, n: int = 10) -> list[dict]:
        return [c.brief(ocr_chars=1500) for c in self.db.inbox(max(1, min(n, 50)))]

    def file_capture(self, capture_id: str, kind: str, summary: str, tags: list[str]) -> dict:
        return self.db.file(capture_id, kind, summary.strip(), [t.strip() for t in tags if t.strip()]).brief()

    # ---- calendar -------------------------------------------------------
    def add_event(self, capture_id: str, title: str, start: str, end: str | None, place: str | None) -> dict:
        cap = self._require(capture_id)
        ev = calendars.build_event(title, start, end, place, notes=f"album-mcp capture: {capture_id}\n{cap.path}")
        backend = self.calendar.name
        start_iso = ev.start.isoformat()
        dup = self.db.find_event(capture_id, backend, start_iso)
        if dup:
            return {"status": "already_added", "backend": backend, "event_ref": dup["event_ref"]}
        ref = self.calendar.add(ev)
        self.db.record_event(capture_id, backend, ref, ev.title, start_iso, ev.end.isoformat(), ev.place)
        return {
            "status": "created",
            "backend": backend,
            "calendar": self.cfg.calendar_name if backend == "apple" else self.cfg.google_calendar_id if backend == "google" else str(self.cfg.ics_dir),
            "event_ref": ref,
            "title": ev.title,
            "start": start_iso,
            "end": ev.end.isoformat(),
            "place": ev.place,
        }

    # ---- retrieval ------------------------------------------------------
    def search(self, query: str, kind: str | None = None, since: str | None = None, until: str | None = None, limit: int = 20) -> list[dict]:
        if until and len(until) == 10:
            until += "T23:59:59"
        caps = self.db.all_for_search(kind, since, until)
        out = []
        for c, s, hits in search.rank(caps, query, min(limit, 50)):
            d = c.brief(ocr_chars=200)
            d["score"] = round(s, 1)
            d["matched"] = hits
            out.append(d)
        return out

    def _require(self, capture_id: str) -> Capture:
        c = self.db.get(capture_id)
        if not c:
            raise KeyError(f"unknown capture id {capture_id}")
        return c

    def _resolve(self, capture_id: str) -> dict | None:
        """Indexed capture from the DB, or any Photos library photo by `photos:<uuid>`."""
        c = self.db.get(capture_id)
        if c:
            return {"capture": c, "path": c.path, "filename": c.filename, "created_at": c.created_at,
                    "size": [c.width, c.height], "file_size": c.size_bytes}
        if capture_id.startswith("photos:"):
            try:
                it = self.photos_source().get(capture_id.split(":", 1)[1])
            except SourceUnavailable:
                return None
            if it:
                return {"capture": None, "path": it.path, "filename": it.filename,
                        "created_at": it.created_at.isoformat(timespec="seconds"),
                        "size": [it.width, it.height], "file_size": it.size_bytes, "labels": it.labels}
        return None

    def find_photos(self, labels: list[str], since: str | None = None, until: str | None = None, limit: int = 40) -> list[dict]:
        if until and len(until) == 10:
            until += "T23:59:59"
        items = self.photos_source().find(
            labels,
            datetime.fromisoformat(since) if since else None,
            datetime.fromisoformat(until) if until else None,
            max(1, min(limit, 200)),
        )
        return [{"id": it.id, "created_at": it.created_at.isoformat(timespec="seconds"),
                 "filename": it.filename, "labels": it.labels} for it in items]

    def look_at(self, ids: list[str]) -> tuple[bytes, list[dict]]:
        found = []
        for i in ids[:16]:
            r = self._resolve(i)
            if r and Path(r["path"]).exists():
                found.append((i, r))
        if not found:
            raise KeyError("none of the ids exist")
        legend = [{"n": n + 1, "id": i, "created_at": r["created_at"],
                   "summary": r["capture"].summary if r["capture"] else None} for n, (i, r) in enumerate(found)]
        return preview.grid([r["path"] for _, r in found]), legend

    def get_photo(self, capture_id: str, max_side: int = 1600) -> tuple[bytes, dict]:
        r = self._resolve(capture_id)
        if not r:
            raise KeyError(f"unknown capture id {capture_id}")
        data, (w, h) = preview.to_jpeg(r["path"], max_side=max_side, quality=90)
        if r["capture"]:
            meta = r["capture"].brief(ocr_chars=4000)
        else:
            meta = {"id": capture_id, "created_at": r["created_at"], "filename": r["filename"],
                    "labels": r["labels"], "indexed": False}
        meta.update({"path": r["path"], "original_size": r["size"], "file_size": r["file_size"], "returned_size": [w, h]})
        return data, meta

    def export_photos(self, ids: list[str], folder: str) -> list[str]:
        dest = Path(folder).expanduser()
        dest.mkdir(parents=True, exist_ok=True)
        out = []
        for i in ids:
            r = self._resolve(i)
            if not r or not Path(r["path"]).exists():
                continue
            stem, ext = Path(r["filename"]).stem, Path(r["path"]).suffix
            base = f"{stem}_{i.replace(':', '-')}"
            target = dest / f"{base}{ext}"
            n = 1
            while target.exists():  # never overwrite (Req 10.7)
                target = dest / f"{base}_{n}{ext}"
                n += 1
            shutil.copy2(r["path"], target)
            out.append(str(target))
        return out

    def status(self) -> dict:
        return {
            **self.db.stats(),
            "sources": self.cfg.sources,
            "folders": self.cfg.folders,
            "calendar_backend": self.cfg.calendar,
            "last_sync": self.db.get_state("last_sync"),
            "db": str(self.cfg.db_path),
        }
