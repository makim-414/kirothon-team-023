# Rollcall

일하는 앨범 MCP (the album MCP that works for you)

Demo: _(녹화 데모 링크 추가 예정)_

캡쳐만 하세요. Rollcall이 스크린샷을 읽고 분류해서, 날짜가 있으면 캘린더에 넣고, 나중에 "그때 캡쳐한 그거"라고 물으면 찾아 줍니다.

## 문제 정의

우리는 하루에도 여러 번 "나중에 봐야지" 하며 화면을 캡쳐합니다. 밋업 초대, 예약 확인, 영수증, 와이파이 비번, 좋은 글귀. 그런데 캡쳐는 앨범에 쌓이기만 합니다.

- **다시 못 찾는다.** 앨범 검색은 날짜와 "스크린샷" 정도만 압니다. "지난달 캡쳐한 카페 영수증"은 수백 장을 스크롤해야 나옵니다.
- **일정이 캘린더로 안 간다.** 초대장을 캡쳐해 놓고 캘린더 등록은 잊어서 일정을 놓칩니다.
- **정리할 시간이 없다.** 앨범 정리는 아무도 하지 않습니다.

캡쳐는 "기억해 줘"라는 의도인데, 지금의 앨범은 그 의도를 처리하지 않습니다.

## 핵심 기능

| 기능 | 설명 |
|---|---|
| 자동 수집 | macOS Photos 스크린샷 + 일반 폴더(안드로이드 동기화 폴더 포함)에서 새 캡쳐를 찾습니다 |
| 온디바이스 OCR | Apple Vision으로 한국어/영어 텍스트를 Mac 안에서 추출합니다 (장당 약 0.5초) |
| AI 분류 | Kiro가 각 캡쳐를 event / insight / reference / other로 나누고 한국어 요약과 한·영 태그를 붙입니다 |
| 캘린더 자동 등록 | 날짜가 있는 캡쳐는 Apple Calendar, Google Calendar, 또는 .ics(Outlook, 네이버 등)로 들어갑니다. 같은 캡쳐는 두 번 등록하지 않습니다 |
| 의미 검색 | 질문을 한·영 동의어로 넓혀 요약, 태그, OCR, Apple 라벨을 함께 검색합니다 |
| 눈으로 고르기 | 후보를 번호 붙은 썸네일 그리드로 보여 주고, AI가 직접 보고 골라 원본을 꺼내 줍니다 |
| 완전 자동 모드 | launchd가 스크린샷 폴더를 지켜보다가 새 캡쳐가 생기면 Kiro CLI로 분류와 등록까지 끝냅니다 |

MCP 도구: `sync_captures`, `inbox`, `file_capture`, `add_event`, `search`, `look_at`, `get_photo`, `export_photos`, `album_status`

## 사용 시나리오

1. **밋업 초대장 캡쳐 → 캘린더**
   카톡으로 받은 밋업 공지를 캡쳐합니다. 몇 초 뒤 Rollcall이 "AWSKRUG 11월 정기 밋업, 11/27(금) 19:00–21:00, AWS Korea 18층"을 "Rollcall" 캘린더에 넣습니다. 캡쳐 id가 일정 메모에 남아 원본으로 바로 돌아갈 수 있습니다.
2. **"지난달 캡쳐한 카페 영수증 찾아줘"**
   Kiro가 `영수증 receipt 카페 cafe 결제 스타벅스`로 검색하고, 후보 썸네일을 본 뒤 맞는 영수증을 보여 줍니다.
3. **"전에 캡쳐한 와이파이 비번"**
   OCR 텍스트에 SSID와 비밀번호가 있어 바로 찾습니다.
4. **"디자인 레퍼런스 모아서 바탕화면 refs 폴더에"**
   insight로 분류된 캡쳐 중 디자인 관련을 골라 폴더로 내보냅니다.

## 기대 효과

- 캡쳐 한 번으로 일정 등록까지 끝나 "캡쳐해 놓고 잊은 일정"이 사라집니다.
- 앨범을 스크롤하는 대신 말로 물어서 몇 초 만에 찾습니다.
- 정리를 따로 하지 않아도 모든 캡쳐에 요약과 태그가 붙습니다.

## 차별점

- **프라이버시:** 사진 원본과 OCR, 인덱스는 Mac 안의 SQLite에만 저장됩니다. 외부 비전 API나 클라우드 벡터 DB를 쓰지 않습니다. Photos 라이브러리는 읽기 전용으로 엽니다(osxphotos가 DB 사본을 읽음).
- **AI가 직접 본다:** 임베딩 점수에만 기대지 않고, 후보 썸네일 그리드를 AI가 보고 고릅니다. OCR이 없는 사진도 찾을 수 있습니다.
- **어디서든 쓴다:** MCP 서버라서 Kiro, Claude Desktop 등 MCP를 지원하는 어떤 어시스턴트에도 붙습니다. 안드로이드 캡쳐와 Google/Outlook 캘린더 사용자도 지원합니다.
- **캡쳐만 하면 끝:** launchd 감시 + Kiro CLI 헤드리스 실행으로 사용자가 아무것도 열지 않아도 처리됩니다.

## 구조

```
캡쳐 (Photos / 스크린샷 폴더 / 안드로이드 동기화 폴더)
   │  sync_captures: 새 파일 탐지 → Apple Vision OCR → SQLite
   ▼
Kiro (steering: .kiro/steering/rollcall.md)
   │  inbox → look_at → file_capture   (분류, 요약, 태그)
   │  add_event                        (Apple / Google / .ics)
   │  search → look_at → get_photo     (찾기)
   ▼
~/.album-mcp/album.db   (로컬 전용)
```

| 파일 | 역할 |
|---|---|
| `src/album_mcp/server.py` | MCP 서버 (stdio), 도구 정의, 요청 id 로깅 |
| `src/album_mcp/core.py` | 설정, 동기화, 분류, 검색, 이벤트 로직 |
| `src/album_mcp/sources.py` | Photos(osxphotos) / 폴더 소스 |
| `src/album_mcp/ocr.py` | Apple Vision OCR (ko/en) |
| `src/album_mcp/calendars.py` | Apple(AppleScript) / Google API / .ics 백엔드 |
| `src/album_mcp/search.py` | 필드 가중치 검색 (한국어 OCR 띄어쓰기 보정) |
| `src/album_mcp/preview.py` | 번호 썸네일 그리드, JPEG 변환 |
| `src/album_mcp/cli.py` | `sync`, `status`, `process`, `install-agent` 명령 |

## 설치와 실행

요구 사항: macOS 13+, [uv](https://docs.astral.sh/uv/), Kiro (IDE 또는 CLI)

```bash
git clone https://github.com/makim-414/team-023.git
cd team-023
uv sync
uv run pytest -q          # 8 passed
```

### 1. Kiro에 연결

이 레포를 Kiro로 열면 `.kiro/settings/mcp.json`의 `rollcall` 서버가 자동으로 뜹니다. 다른 위치에 클론했다면 `--directory` 경로를 고쳐 주세요.

```json
"rollcall": {
  "command": "uv",
  "args": ["run", "--directory", "/path/to/team-023", "album-mcp"],
  "env": { "ALBUM_MCP_FOLDERS": "~/Pictures/Screenshots", "ALBUM_MCP_CALENDAR": "apple" }
}
```

Claude Desktop은 `~/Library/Application Support/Claude/claude_desktop_config.json`의 `mcpServers`에 같은 내용을 넣으면 됩니다.

Kiro 채팅에서 "캡쳐 정리해줘", "지난주 캡쳐한 영수증 찾아줘"처럼 말하면 됩니다.

### 2. macOS 권한

| 권한 | 필요한 곳 | 설정 위치 |
|---|---|---|
| 전체 디스크 접근 | Photos 라이브러리 읽기 | 시스템 설정 → 개인정보 보호 및 보안 → 전체 디스크 접근 권한 → Kiro(또는 터미널) |
| 자동화 → 캘린더 | Apple Calendar 등록 | 첫 등록 때 뜨는 팝업에서 허용 |

전체 디스크 접근 없이도 폴더 소스는 동작합니다.

### 3. 완전 자동 모드 (캡쳐만 하면 끝)

```bash
uv run album-mcp install-agent          # 스크린샷 폴더 감시 + 30분마다 실행
tail -f ~/.album-mcp/agent.log
uv run album-mcp uninstall-agent        # 끄기
```

새 캡쳐가 생기면 `album-mcp process`가 OCR 후 `kiro-cli chat --no-interactive`로 분류와 캘린더 등록을 끝냅니다.

### 설정 (환경 변수)

| 변수 | 기본값 | 설명 |
|---|---|---|
| `ALBUM_MCP_SOURCES` | `photos` (폴더 지정 시 `photos,folder`) | 사용할 소스 |
| `ALBUM_MCP_FOLDERS` | – | 이미지 폴더, `:`로 구분 |
| `ALBUM_MCP_PHOTOS_LIBRARY` | `~/Pictures/Photos Library.photoslibrary` | Photos 라이브러리 경로 |
| `ALBUM_MCP_CALENDAR` | `apple` | `apple` / `google` / `ics` |
| `ALBUM_MCP_CALENDAR_NAME` | `Rollcall` | Apple 캘린더 이름 (없으면 생성) |
| `ALBUM_MCP_GOOGLE_CALENDAR_ID` | `primary` | Google 캘린더 id |
| `ALBUM_MCP_ICS_DIR` | `~/.album-mcp/events` | .ics 저장 폴더 |
| `ALBUM_MCP_DB` | `~/.album-mcp/album.db` | 로컬 인덱스 |

### 안드로이드 캡쳐

폰의 `Pictures/Screenshots`를 Mac 폴더로 동기화하고 그 경로를 `ALBUM_MCP_FOLDERS`에 추가합니다.

- Google Drive for desktop: 폰에서 Drive 백업 → Mac의 `~/Google Drive/...` 폴더 지정
- USB/adb: `adb pull /sdcard/Pictures/Screenshots ~/Pictures/Android`

### 캘린더 선택

- **Apple Calendar (기본):** 별도 설정 없음. macOS 캘린더에 Google 계정을 추가해 두었다면 `ALBUM_MCP_CALENDAR_NAME`에 그 Google 캘린더 이름을 넣어 바로 Google에 등록할 수도 있습니다.
- **Google Calendar API:** `uv sync --extra google` → Google Cloud Console에서 데스크톱 OAuth 클라이언트를 만들어 `~/.config/album-mcp/google_client.json`에 저장 → `uv run album-mcp google-login` → `ALBUM_MCP_CALENDAR=google`. 토큰은 레포 밖에 0600 권한으로 저장됩니다.
- **그 외 (Outlook, 네이버 등):** `ALBUM_MCP_CALENDAR=ics`. 표준 .ics 파일을 만들어 기본 캘린더 앱으로 엽니다.

## Kiro 활용

spec(`.kiro/specs/album-mcp`), steering(`.kiro/steering/rollcall.md`), hook(`.kiro/hooks/`), MCP 설정을 모두 커밋했습니다. 자세한 내용은 [BUILD_REPORT.md](BUILD_REPORT.md)를 보세요.

## 팀

team-023 파소
