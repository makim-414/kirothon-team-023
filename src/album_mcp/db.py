"""Local SQLite store for capture metadata, classifications and created events."""

from __future__ import annotations

import json
import logging
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

KINDS = ("event", "insight", "reference", "other")
SUMMARY_MAX = 200

# Each entry migrates from version i to i+1.
MIGRATIONS: list[str] = [
    """
    CREATE TABLE captures (
        id          TEXT PRIMARY KEY,          -- photos:<uuid> | folder:<sha1>
        source      TEXT NOT NULL,
        path        TEXT NOT NULL,
        filename    TEXT NOT NULL,
        created_at  TEXT NOT NULL,             -- ISO 8601, local time
        width       INTEGER,
        height      INTEGER,
        size_bytes  INTEGER,
        ocr_text    TEXT NOT NULL DEFAULT '',
        labels      TEXT NOT NULL DEFAULT '[]', -- JSON list (Apple labels)
        kind        TEXT,                       -- NULL = not classified yet
        summary     TEXT,
        tags        TEXT NOT NULL DEFAULT '[]', -- JSON list
        filed_at    TEXT
    );
    CREATE INDEX idx_captures_created ON captures(created_at);
    CREATE INDEX idx_captures_kind ON captures(kind);
    CREATE TABLE events (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        capture_id  TEXT NOT NULL REFERENCES captures(id),
        backend     TEXT NOT NULL,
        event_ref   TEXT NOT NULL,
        title       TEXT NOT NULL,
        start       TEXT NOT NULL,
        end         TEXT NOT NULL,
        place       TEXT,
        created_at  TEXT NOT NULL
    );
    CREATE UNIQUE INDEX idx_events_capture ON events(capture_id, backend, start);
    CREATE TABLE state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    """,
]
SCHEMA_VERSION = len(MIGRATIONS)


class ValidationError(ValueError):
    pass


@dataclass
class Capture:
    id: str
    source: str
    path: str
    filename: str
    created_at: str
    width: int | None
    height: int | None
    size_bytes: int | None
    ocr_text: str
    labels: list[str]
    kind: str | None
    summary: str | None
    tags: list[str]
    filed_at: str | None

    @classmethod
    def from_row(cls, r: sqlite3.Row) -> "Capture":
        d = dict(r)
        d["labels"] = json.loads(d["labels"])
        d["tags"] = json.loads(d["tags"])
        return cls(**d)

    def brief(self, ocr_chars: int = 400) -> dict:
        """Compact dict for tool output; OCR is truncated to save context."""
        ocr = self.ocr_text
        return {
            "id": self.id,
            "created_at": self.created_at,
            "filename": self.filename,
            "labels": self.labels,
            "ocr_text": ocr if len(ocr) <= ocr_chars else ocr[:ocr_chars] + "…",
            "kind": self.kind,
            "summary": self.summary,
            "tags": self.tags,
        }


class DB:
    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._migrate()

    # ---- schema -------------------------------------------------------
    def _migrate(self) -> None:
        cur = self.conn.execute("PRAGMA user_version").fetchone()[0]
        if cur >= SCHEMA_VERSION:
            return
        backup = None
        if cur > 0:
            backup = self.path.with_suffix(f".v{cur}.bak")
            self.conn.commit()
            shutil.copy2(self.path, backup)
        try:
            for v in range(cur, SCHEMA_VERSION):
                log.info("DB migration %d -> %d", v, v + 1)
                self.conn.executescript(MIGRATIONS[v])
                self.conn.execute(f"PRAGMA user_version = {v + 1}")
            self.conn.commit()
        except Exception:
            log.exception("DB migration failed")
            self.conn.close()
            if backup:
                shutil.copy2(backup, self.path)
                log.error("DB restored from %s", backup)
            raise

    # ---- state --------------------------------------------------------
    def get_state(self, key: str, default: str | None = None) -> str | None:
        r = self.conn.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
        return r[0] if r else default

    def set_state(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO state(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        self.conn.commit()

    # ---- captures -----------------------------------------------------
    def has(self, capture_id: str) -> bool:
        return self.conn.execute("SELECT 1 FROM captures WHERE id=?", (capture_id,)).fetchone() is not None

    def upsert_capture(self, c: dict) -> None:
        """Insert or refresh source metadata; never overwrites a classification."""
        self.conn.execute(
            """INSERT INTO captures(id,source,path,filename,created_at,width,height,size_bytes,ocr_text,labels)
               VALUES(:id,:source,:path,:filename,:created_at,:width,:height,:size_bytes,:ocr_text,:labels)
               ON CONFLICT(id) DO UPDATE SET path=excluded.path, labels=excluded.labels""",
            {**c, "labels": json.dumps(c.get("labels", []), ensure_ascii=False)},
        )
        self.conn.commit()

    def get(self, capture_id: str) -> Capture | None:
        r = self.conn.execute("SELECT * FROM captures WHERE id=?", (capture_id,)).fetchone()
        return Capture.from_row(r) if r else None

    def inbox(self, n: int) -> list[Capture]:
        rows = self.conn.execute(
            "SELECT * FROM captures WHERE kind IS NULL ORDER BY created_at ASC LIMIT ?", (n,)
        ).fetchall()
        return [Capture.from_row(r) for r in rows]

    def count_unfiled(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM captures WHERE kind IS NULL").fetchone()[0]

    def file(self, capture_id: str, kind: str, summary: str, tags: list[str]) -> Capture:
        if kind not in KINDS:
            raise ValidationError(f"kind must be one of {KINDS}, got {kind!r}")
        if len(summary) > SUMMARY_MAX:
            raise ValidationError(f"summary is {len(summary)} chars; max {SUMMARY_MAX}")
        if not all(isinstance(t, str) for t in tags):
            raise ValidationError("tags must be a list of strings")
        if not self.has(capture_id):
            raise KeyError(capture_id)
        self.conn.execute(
            "UPDATE captures SET kind=?, summary=?, tags=?, filed_at=? WHERE id=?",
            (kind, summary, json.dumps(tags, ensure_ascii=False), datetime.now().isoformat(timespec="seconds"), capture_id),
        )
        self.conn.commit()
        return self.get(capture_id)  # type: ignore[return-value]

    def all_for_search(self, kind: str | None, start: str | None, end: str | None) -> list[Capture]:
        q, args = "SELECT * FROM captures WHERE 1=1", []
        if kind:
            q += " AND kind=?"
            args.append(kind)
        if start:
            q += " AND created_at >= ?"
            args.append(start)
        if end:
            q += " AND created_at <= ?"
            args.append(end)
        return [Capture.from_row(r) for r in self.conn.execute(q, args).fetchall()]

    # ---- events -------------------------------------------------------
    def find_event(self, capture_id: str, backend: str, start: str) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM events WHERE capture_id=? AND backend=? AND start=?", (capture_id, backend, start)
        ).fetchone()

    def record_event(self, capture_id: str, backend: str, ref: str, title: str, start: str, end: str, place: str | None) -> None:
        self.conn.execute(
            "INSERT INTO events(capture_id,backend,event_ref,title,start,end,place,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (capture_id, backend, ref, title, start, end, place, datetime.now().isoformat(timespec="seconds")),
        )
        self.conn.commit()

    def stats(self) -> dict:
        rows = self.conn.execute("SELECT COALESCE(kind,'unfiled') k, COUNT(*) n FROM captures GROUP BY k").fetchall()
        ev = self.conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        return {"captures": {r["k"]: r["n"] for r in rows}, "events": ev}
