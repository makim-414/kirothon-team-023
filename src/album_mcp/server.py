"""Rollcall MCP server (stdio). Tools are thin wrappers over core.Album."""

from __future__ import annotations

import functools
import json
import logging
import sys
import threading
import uuid

from mcp.server.mcpserver import Image, MCPServer

from .core import Album

logging.basicConfig(
    stream=sys.stderr,  # stdout carries the MCP protocol
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(rid)s] %(name)s: %(message)s",
)
_old_factory = logging.getLogRecordFactory()
_rid = {"v": "-"}


def _factory(*a, **kw):
    rec = _old_factory(*a, **kw)
    rec.rid = _rid["v"]
    return rec


logging.setLogRecordFactory(_factory)
log = logging.getLogger("album_mcp")

INSTRUCTIONS = """\
Rollcall gives you the user's screenshots/photos (macOS Photos and synced folders,
e.g. Android) with on-device OCR text and Apple labels. You do the understanding.
Workflows:
1. Accumulate: sync_captures -> inbox -> (look_at if OCR is unclear) -> file_capture for each.
2. Events: when a capture has a concrete date (meeting, ticket, reservation, deadline,
   invitation), file it as kind="event" and call add_event. Resolve relative dates
   ("다음주 화요일") against the capture's created_at, not today.
3. Retrieve: expand the user's question into several Korean+English terms and call
   search; then look_at the top hits and pick visually; get_photo to show one.
"""

mcp = MCPServer("rollcall", title="Rollcall", instructions=INSTRUCTIONS)
_album: Album | None = None
# Tools run in worker threads and may be called in parallel; one SQLite
# connection is shared, so serialize calls.
_lock = threading.Lock()


def album() -> Album:
    global _album
    if _album is None:
        _album = Album()
    return _album


def traced(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with _lock:
            return _call(fn, args, kwargs)

    return wrapper


def _call(fn, args, kwargs):
    _rid["v"] = uuid.uuid4().hex[:8]
    log.info("call %s %s", fn.__name__, json.dumps(kwargs, ensure_ascii=False, default=str)[:500])
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        log.exception("%s failed", fn.__name__)
        raise RuntimeError(f"{type(e).__name__}: {e}") from e
    finally:
        _rid["v"] = "-"


@mcp.tool()
@traced
def sync_captures(since: str | None = None, limit: int = 30) -> dict:
    """Find new screenshots/photos and index them (on-device OCR + Apple labels).

    since: ISO date-time; default is where the last sync stopped.
    limit: max new captures to OCR in this call (~0.5s each). If `remaining` > 0, call again.
    """
    return album().sync(since, limit)


@mcp.tool()
@traced
def inbox(count: int = 10) -> list[dict]:
    """Unclassified captures, oldest first, with OCR text and Apple labels. Classify each with file_capture."""
    return album().inbox(count)


@mcp.tool()
@traced
def file_capture(id: str, kind: str, summary: str, tags: list[str]) -> dict:
    """Store your classification of a capture.

    kind: "event" (has a date to put on a calendar), "insight" (idea, quote, article,
    tip worth remembering), "reference" (receipt, ticket, address, code, docs),
    or "other" (memes, accidental shots).
    summary: <=200 chars, Korean, says what it is and why it was captured.
    tags: 3-8 short tags mixing Korean and English synonyms (e.g. ["영수증","receipt","카페"]).
    Re-filing the same id overwrites the previous classification.
    """
    return album().file_capture(id, kind, summary, tags)


@mcp.tool()
@traced
def add_event(capture_id: str, title: str, start: str, end: str | None = None, place: str | None = None) -> dict:
    """Create a calendar event from a capture (backend set by ALBUM_MCP_CALENDAR: apple, google, ics).

    start/end: ISO "2026-11-20T19:00" for timed events or "2026-11-20" for all-day.
    end defaults to start + 1h (timed) or the same day (all-day).
    The same capture+start is never added twice.
    """
    return album().add_event(capture_id, title, start, end, place)


@mcp.tool()
@traced
def search(query: str, kind: str | None = None, since: str | None = None, until: str | None = None, limit: int = 20) -> list[dict]:
    """Search indexed captures. Put several space-separated terms in `query`: the
    user's words plus synonyms in Korean and English (e.g. "영수증 receipt 결제 카드").
    kind filters to event/insight/reference/other. since/until are ISO dates.
    Returns up to 50 results ranked by relevance; use look_at to see them.
    """
    return album().search(query, kind, since, until, limit)


@mcp.tool()
@traced
def look_at(ids: list[str]) -> list:
    """See up to 16 captures as one numbered thumbnail grid (1..n, 4 columns). Unknown ids are skipped."""
    data, legend = album().look_at(ids)
    return [json.dumps(legend, ensure_ascii=False), Image(data=data, format="jpeg")]


@mcp.tool()
@traced
def get_photo(id: str, max_side: int = 1600) -> list:
    """One capture as a JPEG (longest side capped at max_side px) plus its metadata and full OCR text."""
    data, meta = album().get_photo(id, max_side)
    return [json.dumps(meta, ensure_ascii=False), Image(data=data, format="jpeg")]


@mcp.tool()
@traced
def export_photos(ids: list[str], folder: str) -> list[str]:
    """Copy original files of captures into `folder` (created if missing) as {name}_{id}.{ext}."""
    return album().export_photos(ids, folder)


@mcp.tool()
@traced
def album_status() -> dict:
    """Counts per kind, unfiled backlog, events created, configured sources and calendar."""
    return album().status()


def main() -> None:
    mcp.run()
