import os
from datetime import date, datetime
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
    base = datetime(2026, 11, 1, 10, 0).timestamp()
    _img(shots / "a.png", "Starbucks receipt 5,800", base)
    _img(shots / "b.png", "Meeting Nov 20 7pm", base + 60)
    _img(shots / "c.png", "Hello world", base + 120)
    cfg = Config(
        sources=["folder"],
        folders=[str(shots)],
        db_path=tmp_path / "t.db",
        calendar="ics",
        ics_dir=tmp_path / "ics",
        ics_open=False,
    )
    return Album(cfg)


def test_sync_is_incremental_and_ordered(album):
    r = album.sync(limit=2)
    assert len(r["added"]) == 2 and r["remaining"] == 1
    r = album.sync(limit=10)
    assert len(r["added"]) == 1 and r["remaining"] == 0
    assert album.sync()["added"] == []
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
