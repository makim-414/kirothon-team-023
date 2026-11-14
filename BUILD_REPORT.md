# BUILD_REPORT: Rollcall

KIROTHON 2026, team-023 파소. 11:00부터 18:00까지 Kiro IDE 한 세션에서 아이디어 정리부터 구현, 테스트, 문서화까지 진행했습니다.

## Kiro를 쓴 단계

| 단계 | Kiro 기능 | 한 일 | 결과물 |
|---|---|---|---|
| 아이디어 정리 | 채팅 | "캡쳐만 하면 앨범이 알아서 분류하고 캘린더에 넣고 찾아 주는 MCP" 아이디어를 앨범 검색 + 캡쳐→캘린더로 나누고, 둘을 하나의 MCP로 합치기로 결정 | 범위 합의 |
| 행사 가이드 확인 | 웹 fetch | Notion 가이드에서 제출 파일(README, BUILD_REPORT, .kiro/, PRESENTATION.pdf)과 심사 기준 확인 | 제출 체크리스트 |
| 요구사항 | Spec (requirements-first) | 17개 요구사항(EARS 형식): 동기화, OCR, 분류, 캘린더, 검색, 미리보기, 로컬 전용, 읽기 전용 등. 이후 안드로이드/다중 캘린더 요구로 Req 18–19 추가 | `.kiro/specs/album-mcp/requirements.md` |
| 기술 검증 | 셸 실행 | osxphotos로 Photos 접근 시도 → 전체 디스크 접근 권한 문제 발견, 폴더 소스를 대안으로 설계. ocrmac이 한국어를 지원하지 않는 것을 확인하고 pyobjc로 Vision을 직접 호출(실측 장당 0.03–1.3초) | `ocr.py`, `sources.py` |
| SDK 대응 | 셸 + 소스 읽기 | 설치된 mcp 2.3.0에서 FastMCP가 MCPServer로 바뀐 것을 패키지 소스에서 확인하고 새 API로 작성 | `server.py` |
| 구현 | 에이전트 코딩 | DB(마이그레이션, 백업 복원), 검색(한국어 OCR 띄어쓰기 보정), 캘린더 3종(AppleScript, Google API, RFC 5545 .ics), 썸네일 그리드 | `src/album_mcp/*` |
| 실제 환경 검증 | launchd + Kiro CLI 헤드리스 | 감시 폴더에 예약 확인 캡쳐를 넣자 약 90초 만에 사람 조작 없이 분류되고 실제 Apple Calendar "Rollcall" 캘린더에 일정 생성. 생성된 일정을 AppleScript로 다시 읽어 필드 확인 | `tasks.md` 14.2, 14.5 |
| 실제 보관함 연동 | MCP 도구 호출 | 전체 디스크 접근 권한 후 Photos 보관함 42,147장 로딩 7.6초. Kiro가 `sync_captures(limit=20)` → `inbox` → `look_at`(OCR이 불분명한 10장) → `file_capture` 30건 실행 (event 1, insight 9, reference 10, other 10) | `tasks.md` 14.1 |
| 일정 확인 단계 | 채팅 | 일정 후보(아이언트 대금 11/13 지급)는 등록 전에 사용자에게 먼저 보여 줌. 사용자 확인 전에는 `add_event` 호출하지 않음 | 대화 기록 |
| 기능 추가 (사용자 요청) | Spec 갱신 + 구현 | "내 차 사고 난 사진"을 못 찾는 문제 → `find_photos` 도구 추가, sync 기본값을 최근 30일·최신순으로 변경. tasks.md 19–21, requirements.md 표시, design.md, steering을 같이 갱신 | `sources.py`, `core.py`, `tasks.md` 19–21 |
| 실제 검색 검증 | MCP 도구 + 이미지 판독 | "차 사고 난 내 차 사진": `search` 실패 → `find_photos(["Bumper"])` 129장 → `look_at` 그리드를 직접 보고 파손 사진 14장(2024-07-03, 2024-11-08~11 두 건) 선택 | `tasks.md` 20 |
| 성능 측정 | 셸 실행 | 실제 스크린샷 211장 인덱싱 44초(장당 0.21초), 검색 4–5ms | `tasks.md` 14.4 |
| 테스트 | 셸 실행 | 합성 이미지로 동기화, OCR, 검증, 검색 순위, .ics 생성, 중복 방지, 마이그레이션, 가짜 Photos 보관함으로 find_photos·캐시 갱신 테스트 | `tests/test_core.py` (10 passed) |
| MCP 연동 | MCP 설정 | 워크스페이스 `mcp.json`에 `rollcall` 서버 등록, MCP 클라이언트로 도구 9개 목록과 실제 스크린샷 동기화 확인 | `.kiro/settings/mcp.json` |
| AI 사용 규칙 | Steering | 분류 기준표, 3가지 워크플로(분류, 캘린더, 찾기), 상대 날짜는 캡쳐 시각 기준으로 해석, 검색어 한·영 확장 규칙 | `.kiro/steering/rollcall.md` |
| 자동화 | Hook | 세션 시작 시 새 캡쳐를 OCR 인덱싱하고, 미분류가 있으면 에이전트에게 알림 | `.kiro/hooks/rollcall-sync-on-start.json` |
| 완전 자동 | Kiro CLI 헤드리스 | launchd가 스크린샷 폴더를 감시 → `kiro-cli chat --no-interactive --trust-tools=@rollcall/...`로 분류와 등록. 처음엔 `@rollcall` 패턴이 승인되지 않아 도구별로 명시해 해결 | `cli.py` (`process`, `install-agent`) |
| 설계 정리 | Spec (design) | 구현을 마친 뒤 실제 코드 구조(sources, ocr, db, search, preview, calendars, server, cli)를 기준으로 설계 문서 작성 | `.kiro/specs/album-mcp/design.md` |
| 할 일 정리 | Spec (tasks) | 커밋 기록을 기준으로 끝난 작업 13개는 완료로, 실제 환경 검증·데모·README 마무리·제출은 미완료로 정리 | `.kiro/specs/album-mcp/tasks.md` |
| 요구사항 대조 | Spec (requirements) | 구현과 기준을 하나씩 대조해 구현하지 않은 기준에 **[이번 범위 제외]**, 다르게 구현한 기준에 **[구현 변경]** 표시 | `.kiro/specs/album-mcp/requirements.md` |
| 문서 | 에이전트 작성 | README, 이 보고서, 발표자료 | `README.md`, `BUILD_REPORT.md`, `PRESENTATION.pdf` |

## 설계 결정

| 결정 | 고른 것 | 대안 | 이유 |
|---|---|---|---|
| 의미 이해 | MCP를 쓰는 AI(Kiro)가 직접 분류·요약·태그 | Twelve Labs, 외부 비전 API, 임베딩 | Twelve Labs는 영상용. 외부 API는 사진이 Mac 밖으로 나가고 키 관리가 필요. 이미 대화 중인 AI가 OCR과 썸네일을 보는 편이 단순하고 정확 |
| 검색 | 필드 가중치 키워드 + AI의 질의 확장 + 썸네일로 최종 선택 | 벡터 DB (Chroma, Pinecone) | 분류 시 AI가 한·영 태그를 붙이므로 키워드로 충분. 의존성과 모델 다운로드 없음. 실제 스크린샷 211장에서 검색 4–5ms |
| OCR | Apple Vision (pyobjc 직접) | ocrmac, Tesseract | ocrmac은 한국어 옵션을 막음. Vision은 온디바이스, 무료, 한국어 품질 좋음 |
| Photos 접근 | osxphotos (DB 사본 읽기) | PhotoKit | 읽기 전용 보장, Apple 라벨·iCloud 미리보기 경로까지 제공 |
| 소스 | Photos + 폴더 | Photos 전용 | 안드로이드는 폴더 동기화로 지원, 권한 없이도 동작 |
| 캘린더 | Apple / Google / .ics 선택 | Google 전용 | 사용자마다 쓰는 캘린더가 다름. .ics는 Outlook·네이버 등 어디서나 열림 |
| 자동 실행 | launchd WatchPaths + Kiro CLI | 상주 데몬 | 캡쳐 순간에만 깨어나고, 판단은 같은 steering을 쓰는 Kiro가 함 |

## 안전장치

- 사진, OCR, 인덱스는 로컬 SQLite(`~/.album-mcp/album.db`)에만 저장, 레포에 커밋되지 않음(.gitignore)
- Photos 라이브러리는 읽기 전용(osxphotos가 DB 사본을 읽음), 쓰기 도구 없음
- 헤드리스 실행은 rollcall 도구만 신뢰(`--trust-all-tools` 사용 안 함)
- Google 토큰은 레포 밖 `~/.config/album-mcp`에 0600 권한
- 같은 캡쳐·시작 시각의 일정은 두 번 등록하지 않음

## 개발 과정에서 바뀐 점

### 작업 순서: 요구사항 → 구현 → 설계·할 일 정리

Spec은 requirements-first로 시작했지만 design → tasks 순서를 지키지 않았습니다. 실제 순서는 이렇습니다.

1. **요구사항 작성:** 구현 전에 `requirements.md`(Requirement 1–17)를 썼습니다.
2. **구현 먼저:** 해커톤 시간(6시간) 안에 작동하는 결과를 먼저 확보하려고, design.md와 tasks.md 없이 바로 구현했습니다. 기술 검증(Photos 권한, 한국어 OCR, mcp 2.x API)에서 막히는 지점을 빨리 찾는 것이 더 급했습니다.
3. **요구사항 추가:** 구현 중 사용자 요청으로 안드로이드와 다른 캘린더 지원이 생겨 Requirement 18–19를 추가했습니다.
4. **설계·할 일 정리는 나중에:** 구현과 테스트를 마친 뒤 실제 코드를 기준으로 `design.md`와 `tasks.md`를 작성했습니다. 따라서 design.md는 사전 설계가 아니라 구현 결과를 정리한 문서이고, tasks.md의 완료 표시는 커밋 기록을 기준으로 했습니다.
5. **요구사항 대조:** 마지막에 requirements.md를 실제 코드와 대조했습니다. 구현하지 않은 기준은 **[이번 범위 제외]**, 다르게 구현한 기준은 **[구현 변경]**으로 표시했습니다.

이 순서 때문에 요구사항과 구현 사이에 차이가 꽤 생겼습니다. 예를 들어 검색 가중치(요구사항은 summary 4·tags 3, 구현은 tags 4·summary 3), look_at 최대 개수(50 → 16), DB 기본 경로가 다릅니다. 다음에는 구현 전에 design.md를 먼저 써서 이런 차이를 미리 맞추겠습니다.

### 계획에서 바뀐 내용

| 처음 계획 | 바꾼 것 | 이유 |
|---|---|---|
| Twelve Labs나 비전 API로 의미 검색 | 호출하는 AI(Kiro)가 OCR과 썸네일을 보고 판단 | Twelve Labs는 영상용이고, 외부 API는 사진이 Mac 밖으로 나감 |
| ChromaDB 같은 벡터 DB | SQLite + 필드 가중치 검색 + AI 질의 확장 | 분류할 때 AI가 한·영 태그를 붙이므로 키워드 검색으로 충분 |
| macOS Photos 전용 | Photos + 이미지 폴더 소스 | Photos는 전체 디스크 접근 권한이 필요하고, 안드로이드 사용자도 지원하려고 |
| Google Calendar 전용 | Apple / Google / .ics 중 선택 | 사용자마다 쓰는 캘린더가 다름 |
| 스크린샷만 다루기 | 스크린샷은 색인·분류, 일반 사진은 `find_photos`로 색인 없이 찾기 | "내 차 사고 난 사진"처럼 캡쳐가 아닌 사진도 찾아야 함. 4만 장을 모두 OCR하는 것은 시간 낭비 |
| 동기화는 마지막 시점 이후, 오래된 순 | 최근 30일, 최신순 | 처음 연결한 사용자는 최근 캡쳐부터 정리되길 원함 |
| 30분 주기 Kiro hook | SessionStart hook + launchd(폴더 감시) + Kiro CLI 헤드리스 | Kiro hook에는 시간 주기 트리거가 없음. launchd는 캡쳐가 생기는 순간 실행 가능 |
| 캘린더 이름 "앨범 MCP" | "Rollcall" | 서비스 이름을 Rollcall로 정함 |

## 어려웠던 점과 해결 방법

| 문제 | 해결 |
|---|---|
| osxphotos가 Photos 라이브러리를 열지 못함 (`Operation not permitted`) | macOS 전체 디스크 접근 권한 문제. 폴더 소스를 추가해 권한 없이도 동작하게 하고, Photos 소스는 권한 안내 오류를 돌려주도록 함 |
| ocrmac이 `ko-KR`을 거부함 | pyobjc로 `VNRecognizeTextRequest`를 직접 호출 |
| `mcp` 2.3.0에서 `mcp.server.fastmcp`가 없음 | 설치된 패키지 소스를 읽어 `MCPServer` API로 작성 |
| 한국어 OCR이 "이 런 것"처럼 음절을 띄움 | 검색할 때 공백을 지우고 비교 |
| 헤드리스 Kiro CLI가 `--trust-tools=@rollcall`로 도구를 승인하지 않음 | `@rollcall/sync_captures`처럼 도구별로 나열 (`--trust-all-tools`는 쓰지 않음) |
| 헤드리스 실행에서 병렬 도구 호출 2건 실패 (Kiro가 재시도해 결과는 정상) | 원인을 스레드 간 공유 SQLite 연결로 보고 도구 호출을 락으로 직렬화. 이후 병렬 10개 호출에서 오류 0 (원래 실패 메시지는 남지 않아 원인은 추정) |
| 첫 Photos sync가 2017년 캡쳐부터 시작함 (watermark가 없으면 가장 오래된 것부터) | 기본값을 "최근 30일, 최신순"으로 바꾸고 이미 색인한 것은 건너뛰게 함 |
| 스크린샷만 색인해서 일반 사진(차 사고 사진)을 못 찾음 | 색인 없이 보관함 전체를 Apple 라벨·날짜로 거르는 `find_photos` 추가. Apple에는 "사고" 라벨이 없어 Bumper 같은 물체 라벨로 후보를 뽑고 파손 여부는 AI가 그리드를 보고 판단 |
| `look_at`이 없는 파일을 건너뛰어 그리드 번호가 입력 순서와 어긋남. 검증 중 다른 사진을 고를 뻔함 | 함께 오는 번호↔id 범례로 읽도록 steering에 명시 |
| 보관함을 메모리에 한 번만 읽으면 오래 켜진 서버가 새 사진을 못 봄 | 5분마다 다시 읽기 (`ALBUM_MCP_PHOTOS_REFRESH`) |
| 2×2px 이미지에서 Vision이 오류를 냄 | 설계대로 빈 OCR로 저장하고 다음 캡쳐 진행 (211장 중 1장) |
| 아직 못 푼 것 | Google 캘린더 실제 계정 등록은 미검증 (`tasks.md` 14.3) |
