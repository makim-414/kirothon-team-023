# Rollcall

일하는 앨범 MCP (the album MCP that works for you). 화면을 캡쳐해 두고 다시 찾지 못하거나 일정 등록을 잊는 사람을 위해, 캡쳐를 자동으로 분류하고 캘린더에 넣고 말로 찾아 줍니다.

**Demo:** _(녹화 데모 링크 추가 예정)_

캡쳐만 하세요. Rollcall이 스크린샷을 읽고 분류해서, 날짜가 있으면 캘린더에 넣고, 나중에 "그때 캡쳐한 그거"라고 물으면 찾아 줍니다.

---

## 1. 문제 정의

### 대상 사용자

밋업 공지, 예약 확인, 영수증, 와이파이 비번, 좋은 글귀를 "나중에 봐야지" 하며 캡쳐하는 사람. Mac 스크린샷과 macOS Photos를 쓰는 사람이 1차 대상이고, 안드로이드 캡쳐도 폴더 동기화로 지원합니다.

### 문제 상황

- **다시 못 찾는다:** "지난달 캡쳐한 카페 영수증"이 필요할 때, 앨범 검색은 날짜와 "스크린샷" 정도만 알아서 수백 장을 스크롤해야 합니다.
- **일정이 캘린더로 안 간다:** 초대장을 캡쳐해 놓고 캘린더 등록을 잊으면 일정을 놓칩니다.
- **정리할 시간이 없다:** 캡쳐는 계속 쌓이는데 앨범을 정리하는 사람은 없습니다.

### 기존 방식과 한계

| 방식 | 한계 |
|---|---|
| 앨범 스크롤 | 캡쳐가 쌓일수록 오래 걸리고, 무엇을 찾는지 기억해야 함 |
| Photos 검색 (텍스트·사물 인식) | 키워드가 정확히 맞아야 하고, "영수증"과 "결제"처럼 다른 말로 물으면 못 찾음. 캘린더 등록은 직접 |
| 메모 앱에 옮겨 적기 | 캡쳐하는 이유가 "적기 귀찮아서"인데, 결국 또 적어야 함 |
| 클라우드 AI 앨범 | 사진을 외부 서버로 올려야 함 |

### 근거

팀원 Mac 한 대의 `~/Pictures/Screenshots`를 직접 셌습니다 (2026-11-14 측정, `tasks.md` 14.4).

- 2026-06-08 ~ 09-23 약 3.5개월 동안 스크린샷 **211장**, 하루 평균 약 **2장**
- 그중 **130장**(62%)에 20자가 넘는 글자가 있음. 글자로 된 정보를 남기려는 캡쳐가 많다는 뜻
- 211장 모두 폴더에 쌓여만 있었고, 따로 정리하거나 캘린더에 옮긴 기록은 없음

표본은 1명이라 일반화할 수는 없습니다. 더 많은 사용자 조사는 하지 못했습니다.

### 목표

캡쳐 한 번 외에는 아무것도 하지 않아도 캡쳐가 분류되고, 일정은 캘린더에 들어가고, 말로 물으면 몇 초 안에 원본이 나오게 합니다. 사진은 Mac 밖으로 내보내지 않습니다.

---

## 2. 핵심 기능

| 기능 | 해결하는 불편 | 코드 위치 |
|---|---|---|
| 자동 수집: macOS Photos 스크린샷 + 이미지 폴더(안드로이드 동기화 폴더 포함). 기본 최근 30일, 최신순 | 정리할 시간이 없다 | `src/album_mcp/sources.py`, `core.py` `sync` |
| 온디바이스 OCR: Apple Vision으로 한국어·영어 추출 (실측 장당 0.21초) | 다시 못 찾는다 | `src/album_mcp/ocr.py` |
| AI 분류: event / insight / reference / other, 한국어 요약, 한·영 태그 | 정리할 시간이 없다 | `server.py` `file_capture`, `.kiro/steering/rollcall.md` |
| 캘린더 자동 등록: Apple Calendar, Google Calendar, .ics 중 선택, 중복 등록 없음 | 일정이 캘린더로 안 간다 | `src/album_mcp/calendars.py`, `core.py` `add_event` |
| 의미 검색: 질문을 한·영 동의어로 넓혀 요약·태그·OCR·Apple 라벨 검색 (실측 4–5ms) | 다시 못 찾는다 | `src/album_mcp/search.py` |
| 일반 사진 찾기: 스크린샷이 아닌 사진까지 보관함 전체에서 Apple 라벨(Car, Dog 등)과 날짜로 후보를 뽑음. 색인 없이 바로 (실측 4만 2천 장 보관함, 로딩 7.6초) | 다시 못 찾는다 ("내 차 사고 난 사진"처럼 캡쳐가 아닌 사진) | `sources.py` `PhotosSource.find`, `server.py` `find_photos` |
| 눈으로 고르기: 후보를 번호 썸네일 그리드로 보여 주고 AI가 직접 골라 원본 제공 | 다시 못 찾는다 | `src/album_mcp/preview.py`, `server.py` `look_at`, `get_photo` |
| 완전 자동 모드: 새 캡쳐가 생기면 launchd가 Kiro CLI로 분류와 등록을 끝냄 | 셋 모두 (사용자가 아무것도 열지 않음) | `src/album_mcp/cli.py` `process`, `install-agent` |

MCP 도구: `sync_captures`, `inbox`, `file_capture`, `add_event`, `search`, `find_photos`, `look_at`, `get_photo`, `export_photos`, `album_status`

## 3. 사용 시나리오

1. **밋업 초대장 캡쳐 → 캘린더**
   카톡으로 받은 밋업 공지를 캡쳐합니다. 몇 초 뒤 Rollcall이 "AWSKRUG 11월 정기 밋업, 11/27(금) 19:00–21:00, AWS Korea 18층"을 "Rollcall" 캘린더에 넣습니다. 캡쳐 id가 일정 메모에 남아 원본으로 바로 돌아갈 수 있습니다.
2. **"지난달 캡쳐한 카페 영수증 찾아줘"**
   Kiro가 `영수증 receipt 카페 cafe 결제 스타벅스`로 검색하고, 후보 썸네일을 본 뒤 맞는 영수증을 보여 줍니다.
3. **"전에 캡쳐한 와이파이 비번"**
   OCR 텍스트에 SSID와 비밀번호가 있어 바로 찾습니다.
4. **"디자인 레퍼런스 모아서 바탕화면 refs 폴더에"**
   insight로 분류된 캡쳐 중 디자인 관련을 골라 폴더로 내보냅니다.

## 4. 기대 효과

| 항목 | 지금 | Rollcall | 근거 |
|---|---|---|---|
| 캡쳐 후 일정 등록 | 직접 앱을 열어 입력하거나 잊음 | 사용자 조작 0회 | 엔드투엔드 실행에서 밋업 초대장 → 일정 생성 확인 (`BUILD_REPORT.md`) |
| 캡쳐 정리 | 211장 중 분류 0장 | 새 캡쳐마다 자동 분류 | `album-mcp process` |
| 211장 인덱싱 | – | 44초 (장당 0.21초, Mac 안에서) | `tasks.md` 14.4 |
| 검색 응답 | 앨범 스크롤 | 4–5ms + AI가 썸네일로 확인 | `tasks.md` 14.4 |
| 외부로 나가는 사진 | 클라우드 AI 앨범은 원본 업로드 | 0장 (기본 설정 기준) | `design.md` |

## 5. 차별점

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

## 6. 설치와 실행

요구 사항: macOS 13+, [uv](https://docs.astral.sh/uv/), Kiro (IDE 또는 CLI)

```bash
git clone https://github.com/makim-414/kirothon-team-023.git
cd kirothon-team-023
uv sync
```

### 1. Kiro에 연결

이 레포를 Kiro로 열면 `.kiro/settings/mcp.json`의 `rollcall` 서버가 자동으로 뜹니다. 다른 위치에 클론했다면 `--directory` 경로를 고쳐 주세요.

```json
"rollcall": {
  "command": "uv",
  "args": ["run", "--directory", "/path/to/kirothon-team-023", "album-mcp"],
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

## 7. 테스트

```bash
uv run pytest -q     # 8 passed
```

`tests/test_core.py`는 텍스트를 그린 합성 PNG를 임시 폴더에 만들고, `folder` 소스와 `ics` 캘린더로 실제 OCR까지 실행합니다. 사용자 사진이나 캘린더는 건드리지 않습니다.

| 테스트 | 확인하는 것 |
|---|---|
| `test_sync_is_incremental_and_ordered` | 호출당 개수 제한, 증분 동기화, 오래된 순 |
| `test_ocr_runs` | Apple Vision OCR 결과 저장 |
| `test_file_capture_validation` | kind·summary 검증, 재분류 덮어쓰기 |
| `test_search_ranks_tags_and_filters` | 태그 일치 우선 순위, kind·기간 필터 |
| `test_add_event_ics_and_dedupe` | .ics 내용(UTC, 장소), 중복 방지, start > end 거부 |
| `test_build_event_all_day` | 종일 일정 |
| `test_look_at_and_export` | 번호 그리드, 없는 id 건너뛰기, 내보내기 덮어쓰기 방지 |
| `test_db_migration_idempotent` | 스키마 버전, 마이그레이션 재실행 |

테스트 밖에서 직접 확인한 것: MCP 클라이언트로 도구 9개 목록과 병렬 호출 10개(오류 0), 실제 스크린샷 211장 인덱싱, Kiro CLI 헤드리스로 분류와 .ics 일정 생성.
실제 환경에서 확인한 것: Apple Calendar 일정 생성, launchd 자동 모드(새 캡쳐 → 약 90초 뒤 분류와 일정 등록).
아직 확인하지 않은 것: Google 캘린더 실제 계정 등록, 전체 디스크 접근 권한을 준 Photos 소스 (`.kiro/specs/album-mcp/tasks.md` 14번).

---

## Kiro 활용

spec(`.kiro/specs/album-mcp`), steering(`.kiro/steering/rollcall.md`), hook(`.kiro/hooks/`), MCP 설정을 모두 커밋했습니다. 자세한 내용은 [BUILD_REPORT.md](BUILD_REPORT.md)를 보세요.

## 팀

- **팀 번호:** team-023
- **팀명:** 파소

| 이름 | 역할 |
|---|---|
| 김민성 ([@makim-414](https://github.com/makim-414)) | 1인 팀: 기획, 개발, 발표 전부 |
