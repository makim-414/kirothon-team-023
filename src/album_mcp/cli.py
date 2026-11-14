"""Command line entry point.

  album-mcp                 run the MCP server (stdio)
  album-mcp sync [--limit] [--days 30] [--since]  index recent captures, newest first (no AI)
  album-mcp status          counts and config
  album-mcp process         sync, then have Kiro CLI file the inbox and add events
  album-mcp install-agent   run `process` automatically on every new screenshot (launchd)
  album-mcp uninstall-agent
  album-mcp google-login    one-time OAuth for the google calendar backend
"""

from __future__ import annotations

import argparse
import json
import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
LABEL = "dev.rollcall.album-mcp"
PLIST = Path(f"~/Library/LaunchAgents/{LABEL}.plist").expanduser()
LOG = Path("~/.album-mcp/agent.log").expanduser()

TOOLS = ["sync_captures", "inbox", "file_capture", "add_event", "search", "look_at", "get_photo", "album_status"]

PROCESS_PROMPT = """\
Use only the rollcall MCP tools. Follow the Rollcall accumulation and event workflows:
1. Call sync_captures; repeat while remaining > 0 (max 5 times).
2. Call inbox(count=10). For each capture, read OCR text and labels; call look_at on
   the batch if any are unclear. Then call file_capture with kind, a Korean summary
   (<=200 chars) and 3-8 Korean+English tags.
3. For every capture filed as kind="event" with a concrete date, call add_event.
   Resolve relative dates against the capture's created_at.
4. Repeat steps 2-3 until inbox is empty or you have filed 30 captures.
5. Finish with one line: "filed N, events M".
"""


def _print(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def cmd_process(args) -> int:
    from .core import Album

    r = Album().sync(limit=args.limit)
    print(f"synced {len(r['added'])} new, unfiled {r['unfiled_total']}", flush=True)
    for e in r["errors"]:
        print(f"warning [{e['source']}]: {e['error']}", file=sys.stderr)
    if r["unfiled_total"] == 0:
        return 0
    kiro = shutil.which("kiro-cli") or str(Path("~/.local/bin/kiro-cli").expanduser())
    trust = ",".join(f"@rollcall/{t}" for t in TOOLS)
    cmd = [kiro, "chat", "--no-interactive", "--trust-workspace", f"--trust-tools={trust}", PROCESS_PROMPT]
    return subprocess.run(cmd, cwd=PROJECT).returncode


def cmd_install_agent(args) -> int:
    folders = [f for f in os.environ.get("ALBUM_MCP_FOLDERS", "~/Pictures/Screenshots").split(":") if f]
    watch = [str(Path(f).expanduser()) for f in folders]
    uv = shutil.which("uv") or "/opt/homebrew/bin/uv"
    env = {k: v for k, v in os.environ.items() if k.startswith("ALBUM_MCP_")}
    env.setdefault("ALBUM_MCP_FOLDERS", ":".join(watch))
    env["PATH"] = f"{Path(uv).parent}:{Path('~/.local/bin').expanduser()}:/usr/bin:/bin"
    LOG.parent.mkdir(parents=True, exist_ok=True)
    plist = {
        "Label": LABEL,
        "ProgramArguments": [uv, "run", "--directory", str(PROJECT), "album-mcp", "process"],
        "WatchPaths": watch,  # fires when a screenshot lands in the folder
        "StartInterval": args.interval * 60,  # and every N minutes (Photos library, missed events)
        "ThrottleInterval": 30,
        "EnvironmentVariables": env,
        "StandardOutPath": str(LOG),
        "StandardErrorPath": str(LOG),
    }
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["launchctl", "unload", str(PLIST)], capture_output=True)
    PLIST.write_bytes(plistlib.dumps(plist))
    subprocess.run(["launchctl", "load", str(PLIST)], check=True)
    print(f"installed {PLIST}\nwatching {watch}, every {args.interval} min\nlog: {LOG}")
    return 0


def cmd_uninstall_agent(args) -> int:
    subprocess.run(["launchctl", "unload", str(PLIST)], capture_output=True)
    PLIST.unlink(missing_ok=True)
    print("uninstalled")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="album-mcp", description="Rollcall: 일하는 앨범 MCP")
    sub = p.add_subparsers(dest="cmd")
    s = sub.add_parser("sync")
    s.add_argument("--limit", type=int, default=30)
    s.add_argument("--since")
    s.add_argument("--days", type=int, default=30)
    sub.add_parser("status")
    pr = sub.add_parser("process")
    pr.add_argument("--limit", type=int, default=30)
    ia = sub.add_parser("install-agent")
    ia.add_argument("--interval", type=int, default=30, help="minutes (default 30)")
    sub.add_parser("uninstall-agent")
    sub.add_parser("google-login")
    sub.add_parser("serve")
    a = p.parse_args(argv)

    if a.cmd in (None, "serve"):
        from .server import main as serve

        serve()
        return 0
    if a.cmd == "sync":
        from .core import Album

        _print(Album().sync(a.since, a.limit, a.days))
    elif a.cmd == "status":
        from .core import Album

        _print(Album().status())
    elif a.cmd == "process":
        return cmd_process(a)
    elif a.cmd == "install-agent":
        return cmd_install_agent(a)
    elif a.cmd == "uninstall-agent":
        return cmd_uninstall_agent(a)
    elif a.cmd == "google-login":
        from .calendars import GoogleCalendar

        GoogleCalendar()._service()
        print("Google Calendar connected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
