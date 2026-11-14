import os
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

from album_mcp import calendars
from album_mcp.core import Album, Config
from album_mcp.db import DB, ValidationError


def _img(path: Path, text: str, mtime: float):
    im = Image.new("RGB", (900, 300), "white")
    d = ImageDraw.Draw(im)
    font = None
    for f in ("/System/Library/Fonts/AppleSDGothicNeo.ttc", "/System/Library/Fonts/Helvetica.ttc"):
        if os.path.exists(f):
            font = ImageFont.truetype(f, 48)
            break
    d.text((30, 110), text, fill="black", font=font)
    im.save(path)
    os.utime(path, (mtime, mtime))


@pytest.fixture
def album(tmp_path):
    shots = tmp_path / "shots"
    shots.mkdir()
    base = (datetime.now() - timedelta(days=5)).timestamp()
    _img(shots / "a.png", "Starbucks receipt 5,800", base)
    _img(shots / "b.png", "Meeting Nov 20 7pm", base + 60)
    _img(shots / "c.png", "Hello world", base + 120)
    _img(shots / "old.png", "Old capture", (datetime.now() - timedelta(days=60)).timestamp())
    cfg = Config(
        sources=["folder"],
        folders=[str(shots)],
        db_path=tmp_path / "t.db",
        calendar="ics",
        ics_dir=tmp_path / "ics",
        ics_open=False,
    )
    return Album(cfg)


def test_sync_is_recent_newest_first_and_incremental(album):
    r = album.sync(limit=2)
    names = [Path(a["path"]).name for a in r["added"]]
    assert names == ["c.png", "b.png"] and r["remaining"] == 1  # newest first, old.png outside 30 days
    r = album.sync(limit=10)
    assert [Path(a["path"]).name for a in r["added"]] == ["a.png"] and r["remaining"] == 0
    assert album.sync()["added"] == []
    r = album.sync(since=(datetime.now() - timedelta(days=90)).isoformat())
    assert [Path(a["path"]).name for a in r["added"]] == ["old.png"]
    ids = [c["created_at"] for c in album.inbox(10)]
    assert ids == sorted(ids)


def test_ocr_runs(album):
    album.sync()
    texts = " ".join(c["ocr_text"] for c in album.inbox(10)).lower()
    assert "receipt" in texts


def test_file_capture_validation(album):
    album.sync()
    cid = album.inbox(1)[0]["id"]
    with pytest.raises(ValidationError):
        album.file_capture(cid, "nope", "x", [])
    with pytest.raises(ValidationError):
        album.file_capture(cid, "other", "x" * 201, [])
    album.file_capture(cid, "reference", "스타벅스 영수증", ["영수증", "receipt"])
    album.file_capture(cid, "insight", "덮어쓰기", ["tag"])
    assert album.db.get(cid).kind == "insight"
    assert album.db.count_unfiled() == 2


def test_search_ranks_tags_and_filters(album):
    album.sync()
    caps = album.inbox(10)
    album.file_capture(caps[0]["id"], "reference", "카페 결제 영수증", ["영수증", "receipt", "카페"])
    album.file_capture(caps[1]["id"], "event", "11월 20일 저녁 회의", ["회의", "meeting"])
    hits = album.search("영수증 결제 receipt")
    assert hits[0]["id"] == caps[0]["id"]
    assert album.search("회의", kind="reference") == []
    assert album.search("회의", since="2026-12-01") == []


def test_add_event_ics_and_dedupe(album):
    album.sync()
    cid = album.inbox(1)[0]["id"]
    r = album.add_event(cid, "회의", "2026-11-20T19:00", None, "강남")
    assert r["status"] == "created"
    text = Path(r["event_ref"]).read_text()
    assert "BEGIN:VEVENT" in text and "LOCATION:강남" in text and "DTSTART:20261120T100000Z" in text
    assert album.add_event(cid, "회의", "2026-11-20T19:00", None, None)["status"] == "already_added"
    with pytest.raises(ValueError):
        album.add_event(cid, "x", "2026-11-20T19:00", "2026-11-20T18:00", None)


def test_build_event_all_day():
    ev = calendars.build_event("마감", "2026-11-30", None, None, "")
    assert ev.all_day and ev.start == ev.end == date(2026, 11, 30)


def test_look_at_and_export(album, tmp_path):
    album.sync()
    ids = [c["id"] for c in album.inbox(10)]
    data, legend = album.look_at(ids + ["folder:missing"])
    assert data[:2] == b"\xff\xd8" and [x["n"] for x in legend] == [1, 2, 3]
    out = album.export_photos(ids[:2] + ["nope"], str(tmp_path / "exp"))
    assert len(out) == 2 and all(Path(p).exists() for p in out)
    again = album.export_photos(ids[:1], str(tmp_path / "exp"))
    assert again[0] != out[0] and again[0].endswith("_1.png") and Path(out[0]).exists()


def test_db_migration_idempotent(tmp_path):
    DB(tmp_path / "x.db")
    db = DB(tmp_path / "x.db")
    assert db.conn.execute("PRAGMA user_version").fetchone()[0] == 1


class FakePhotosDB:
    def __init__(self, photos):
        self._p = photos

    def photos(self, **kw):
        return self._p

    def get_photo(self, uuid):
        return next((p for p in self._p if p.uuid == uuid), None)


def _photo(uuid, path, when, labels, screenshot=False):
    return SimpleNamespace(uuid=uuid, path=str(path), ismissing=False, path_derivatives=[], original_filename=Path(path).name,
                           date=when, width=900, height=300, original_filesize=1, labels=labels,
                           labels_normalized=[l.lower() for l in labels], screenshot=screenshot)


def test_find_photos_whole_library_and_reuse_ids(album, tmp_path):
    shots = tmp_path / "shots"
    now = datetime.now()
    lib = [
        _photo("CAR1", shots / "a.png", now - timedelta(days=400), ["Car", "Vehicle", "Outdoor"]),
        _photo("CAR2", shots / "b.png", now - timedelta(days=10), ["Automobile"]),
        _photo("DOG1", shots / "c.png", now - timedelta(days=3), ["Dog"]),
        _photo("SHOT", shots / "old.png", now - timedelta(days=1), ["Document"], screenshot=True),
    ]
    src = album.photos_source()
    src._db = FakePhotosDB(lib)
    hits = album.find_photos(["car", "VEHICLE", "automobile"])
    assert [h["id"] for h in hits] == ["photos:CAR2", "photos:CAR1"]  # any label, case-insensitive, newest first
    assert [h["id"] for h in album.find_photos(["Car"], since=(now - timedelta(days=30)).date().isoformat())] == []
    assert album.find_photos(["Car", "Automobile"], limit=1)[0]["id"] == "photos:CAR2"
    assert album.db.count_unfiled() == 0  # nothing indexed
    data, legend = album.look_at([h["id"] for h in hits])
    assert data[:2] == b"\xff\xd8" and [x["id"] for x in legend] == ["photos:CAR2", "photos:CAR1"]
    _, meta = album.get_photo("photos:CAR1")
    assert meta["indexed"] is False and "Car" in meta["labels"]
    out = album.export_photos(["photos:CAR1", "photos:NOPE"], str(tmp_path / "exp"))
    assert len(out) == 1 and Path(out[0]).name == "a_photos-CAR1.png"


def test_photos_cache_refreshes(album, monkeypatch):
    import album_mcp.sources as src_mod
    src = album.photos_source()
    loads = []

    class Lib:
        def __init__(self, path):
            loads.append(path)

        def photos(self, **kw):
            return []

    monkeypatch.setattr("osxphotos.PhotosDB", Lib)
    clock = [1000.0]
    monkeypatch.setattr(src_mod.time, "monotonic", lambda: clock[0])
    src.find(["Car"], None, None, 10)
    src.find(["Car"], None, None, 10)
    assert len(loads) == 1  # cached
    clock[0] += src.REFRESH_SECONDS + 1
    src.find(["Car"], None, None, 10)
    assert len(loads) == 2  # reloaded after the refresh interval
