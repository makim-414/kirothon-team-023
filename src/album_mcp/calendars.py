"""Calendar backends: Apple Calendar (AppleScript), Google Calendar API, .ics file.

Google users have two options:
  * `apple` backend + ALBUM_MCP_CALENDAR_NAME set to a Google calendar that is
    already added in macOS Calendar (no OAuth setup), or
  * `google` backend with an OAuth client file (works without macOS Calendar).
Outlook / Naver / anything else: `ics` backend opens a standard .ics file.
"""

from __future__ import annotations

import logging
import os
import subprocess
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class EventSpec:
    title: str
    start: datetime | date
    end: datetime | date
    place: str | None
    notes: str

    @property
    def all_day(self) -> bool:
        return not isinstance(self.start, datetime)


def parse_when(s: str) -> datetime | date:
    s = s.strip()
    if len(s) == 10:
        return date.fromisoformat(s)
    dt = datetime.fromisoformat(s)
    return dt.astimezone().replace(tzinfo=None) if dt.tzinfo else dt


def build_event(title: str, start: str, end: str | None, place: str | None, notes: str) -> EventSpec:
    if not title.strip():
        raise ValueError("title is required")
    s = parse_when(start)
    if end:
        e = parse_when(end)
    else:
        e = s if not isinstance(s, datetime) else s + timedelta(hours=1)
    if type(s) is not type(e):
        raise ValueError("start and end must both be dates or both be date-times")
    if s > e:
        raise ValueError(f"start {start} is after end {end}")
    return EventSpec(title.strip(), s, e, place or None, notes)


# ---------------------------------------------------------------------------
class AppleCalendar:
    name = "apple"

    SCRIPT = r'''
on mkdate(y, m, d, secs)
    set dt to current date
    set day of dt to 1
    set year of dt to y
    set month of dt to m
    set day of dt to d
    set time of dt to secs
    return dt
end mkdate

on run argv
    set calName to item 1 of argv
    set ttl to item 2 of argv
    set sd to my mkdate((item 3 of argv) as integer, (item 4 of argv) as integer, (item 5 of argv) as integer, (item 6 of argv) as integer)
    set ed to my mkdate((item 7 of argv) as integer, (item 8 of argv) as integer, (item 9 of argv) as integer, (item 10 of argv) as integer)
    set loc to item 11 of argv
    set nts to item 12 of argv
    set isAllDay to (item 13 of argv) is "1"
    tell application "Calendar"
        if not (exists calendar calName) then
            make new calendar with properties {name:calName}
        end if
        tell calendar calName
            set ev to make new event at end with properties {summary:ttl, start date:sd, end date:ed, location:loc, description:nts, allday event:isAllDay}
            return uid of ev
        end tell
    end tell
end run
'''

    def __init__(self, calendar_name: str):
        self.calendar_name = calendar_name

    @staticmethod
    def _parts(d: datetime | date) -> list[str]:
        secs = d.hour * 3600 + d.minute * 60 if isinstance(d, datetime) else 0
        return [str(d.year), str(d.month), str(d.day), str(secs)]

    def add(self, ev: EventSpec) -> str:
        end = ev.end
        if ev.all_day:
            end = ev.end + timedelta(days=1)  # Calendar treats all-day end as exclusive
        args = [
            self.calendar_name,
            ev.title,
            *self._parts(ev.start),
            *self._parts(end),
            ev.place or "",
            ev.notes,
            "1" if ev.all_day else "0",
        ]
        r = subprocess.run(["osascript", "-", *args], input=self.SCRIPT, capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            raise RuntimeError(
                "Calendar AppleScript failed (allow Calendar automation for this app in "
                f"System Settings > Privacy & Security > Automation): {r.stderr.strip()}"
            )
        return r.stdout.strip()


# ---------------------------------------------------------------------------
CONFIG_DIR = Path(os.environ.get("ALBUM_MCP_CONFIG_DIR", "~/.config/album-mcp")).expanduser()


class GoogleCalendar:
    name = "google"
    SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

    def __init__(self, calendar_id: str = "primary"):
        self.calendar_id = calendar_id
        self.client_file = CONFIG_DIR / "google_client.json"
        self.token_file = CONFIG_DIR / "google_token.json"

    def _service(self):
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
        except ImportError as e:
            raise RuntimeError("Install the Google extra: uv sync --extra google") from e

        creds = None
        if self.token_file.exists():
            creds = Credentials.from_authorized_user_file(str(self.token_file), self.SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not self.client_file.exists():
                    raise RuntimeError(
                        f"Google OAuth client file not found at {self.client_file}. "
                        "Create a Desktop OAuth client in Google Cloud Console and save it there, "
                        "then run: uv run album-mcp google-login"
                    )
                flow = InstalledAppFlow.from_client_secrets_file(str(self.client_file), self.SCOPES)
                creds = flow.run_local_server(port=0)
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            self.token_file.write_text(creds.to_json())
            os.chmod(self.token_file, 0o600)
        return build("calendar", "v3", credentials=creds, cache_discovery=False)

    def add(self, ev: EventSpec) -> str:
        if ev.all_day:
            when = {
                "start": {"date": ev.start.isoformat()},
                "end": {"date": (ev.end + timedelta(days=1)).isoformat()},
            }
        else:
            when = {
                "start": {"dateTime": ev.start.astimezone().isoformat()},
                "end": {"dateTime": ev.end.astimezone().isoformat()},
            }
        body = {"summary": ev.title, "description": ev.notes, **when}
        if ev.place:
            body["location"] = ev.place
        created = self._service().events().insert(calendarId=self.calendar_id, body=body).execute()
        return created["id"]


# ---------------------------------------------------------------------------
def _ics_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


class IcsCalendar:
    name = "ics"

    def __init__(self, out_dir: Path, open_file: bool):
        self.out_dir = out_dir
        self.open_file = open_file

    @staticmethod
    def render(ev: EventSpec, uid: str) -> str:
        if ev.all_day:
            ds = f"DTSTART;VALUE=DATE:{ev.start:%Y%m%d}"
            de = f"DTEND;VALUE=DATE:{ev.end + timedelta(days=1):%Y%m%d}"
        else:
            # naive datetimes are local time; store as UTC so every app agrees
            ds = f"DTSTART:{ev.start.astimezone(timezone.utc):%Y%m%dT%H%M%SZ}"
            de = f"DTEND:{ev.end.astimezone(timezone.utc):%Y%m%dT%H%M%SZ}"
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//album-mcp//KO",
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}",
            ds,
            de,
            f"SUMMARY:{_ics_escape(ev.title)}",
            f"DESCRIPTION:{_ics_escape(ev.notes)}",
        ]
        if ev.place:
            lines.append(f"LOCATION:{_ics_escape(ev.place)}")
        lines += ["END:VEVENT", "END:VCALENDAR"]
        return "\r\n".join(lines) + "\r\n"

    def add(self, ev: EventSpec) -> str:
        uid = f"{uuid.uuid4()}@album-mcp"
        self.out_dir.mkdir(parents=True, exist_ok=True)
        path = self.out_dir / f"{ev.start:%Y%m%d}-{uid[:8]}.ics"
        path.write_text(self.render(ev, uid), encoding="utf-8")
        if self.open_file:
            subprocess.run(["open", str(path)], check=False)
        return str(path)


def make_backend(kind: str, *, calendar_name: str, google_calendar_id: str, ics_dir: Path, ics_open: bool):
    if kind == "apple":
        return AppleCalendar(calendar_name)
    if kind == "google":
        return GoogleCalendar(google_calendar_id)
    if kind == "ics":
        return IcsCalendar(ics_dir, ics_open)
    raise ValueError(f"unknown calendar backend {kind!r} (use apple, google, or ics)")
