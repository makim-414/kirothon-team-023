---
inclusion: always
---

# Rollcall: how to use the album tools

Rollcall (`rollcall` MCP server, package `album-mcp`) indexes the user's screenshots and photos
on-device (OCR + Apple labels). You supply the understanding: classification, summaries,
tags, dates. Image data never leaves the Mac except as tool results shown to you.

## Kinds

| kind | use for | examples |
|---|---|---|
| event | has a concrete date/time to put on a calendar | 회의 초대, 공연 티켓, 예약 확인, 마감일, 청첩장 |
| insight | something worth remembering or reading again | 아티클, 명언, 팁, 디자인 레퍼런스, 트윗 |
| reference | facts to look up later | 영수증, 주소, 계좌번호, 코드, 설정 화면, 송장 |
| other | nothing to keep | 밈, 실수로 찍힌 화면, 빈 화면 |

## 1. Accumulate (분류)

1. `sync_captures` — repeat while `remaining > 0`.
2. `inbox(count=10)`.
3. If OCR is empty or ambiguous for any capture, `look_at` the batch once and judge visually.
4. `file_capture(id, kind, summary, tags)` for each:
   - summary: Korean, ≤200 chars, what it is + why the user likely captured it.
   - tags: 3–8, mix Korean and English synonyms (`["영수증","receipt","스타벅스","카페"]`),
     include names of people, places, brands, and the app it came from.

## 2. Events (캘린더)

For each capture filed as `event`:
1. Read the date, time, place, and title from OCR (use `get_photo` if text is cut off).
2. Resolve relative dates ("내일", "다음주 화요일", "this Friday") against the capture's
   `created_at`, never against today. Year missing → the next occurrence after `created_at`.
3. `add_event(capture_id, title, start, end?, place?)`. ISO `2026-11-20T19:00` for timed,
   `2026-11-20` for all-day. Skip it if no concrete date exists; file it as `reference` instead.
4. Tell the user what was added (title, date, place).

## 3. Retrieve (찾기)

1. Expand the request into 4–8 terms: the user's words, synonyms, Korean and English
   (`"그때 캡쳐한 카페 영수증"` → `"영수증 receipt 카페 cafe 결제 카드 스타벅스"`).
2. `search(query, kind?, since?, until?)` — set `since/until` when the user gives a period
   ("지난달", "여름에"). If nothing comes back, try broader terms once.
3. `look_at` the top 8–12 ids, pick the right one(s) visually.
4. `get_photo(id)` to show it, or `export_photos(ids, folder)` if they want files.

## When a tool fails

| tool | error | do |
|---|---|---|
| sync_captures | `errors` has a `photos` entry (Full Disk Access) | continue with the other sources; tell the user once how to grant access |
| sync_captures | any other failure | retry once, then abort and report |
| inbox | any | abort and report |
| look_at | "none of the ids exist" | skip; classify from OCR text |
| file_capture | invalid kind or summary too long | fix the argument and retry once |
| file_capture | unknown id | skip that capture |
| add_event | invalid date / start after end | re-read the capture (`get_photo`), fix, retry once; else file as `reference` and skip |
| add_event | calendar permission / Google setup | abort events for this run; tell the user the setting named in the error |
| add_event | `already_added` | not an error; skip |
| search | empty result | retry once with broader terms; then tell the user nothing matched |
| get_photo / export_photos | unknown id or unreadable file | skip that id and say which ones were skipped |

Never retry a call more than once with the same arguments. A capture that failed to file stays in `inbox` for the next run.

## Examples

- "어제 찍은 캡쳐 정리해줘" → workflow 1, then 2 for events.
- "지난주에 본 회의 일정 캘린더에 넣었어?" → `search("회의 meeting 일정", kind="event", since=...)`.
- "전에 캡쳐한 와이파이 비번" → `search("wifi 와이파이 비밀번호 password")` → `get_photo`.
- "디자인 레퍼런스 모아서 ~/Desktop/refs에" → `search(..., kind="insight")` → `look_at` → `export_photos`.
