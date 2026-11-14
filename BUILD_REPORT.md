# BUILD_REPORT: Rollcall

KIROTHON 2026, team-023 파소. 11:00부터 18:00까지 Kiro IDE 한 세션에서 아이디어 정리부터 구현, 테스트, 문서화까지 진행했습니다.

## Kiro를 쓴 단계

| 단계 | Kiro 기능 | 한 일 | 결과물 |
|---|---|---|---|
| 아이디어 정리 | 채팅 | "캡쳐만 하면 앨범이 알아서 분류하고 캘린더에 넣고 찾아 주는 MCP" 아이디어를 앨범 검색 + 캡쳐→캘린더로 나누고, 둘을 하나의 MCP로 합치기로 결정 | 범위 합의 |
| 행사 가이드 확인 | 웹 fetch | Notion 가이드에서 제출 파일(README, BUILD_REPORT, .kiro/, PRESENTATION.pdf)과 심사 기준 확인 | 제출 체크리스트 |
| 요구사항 | Spec (requirements-first) | 17개 요구사항(EARS 형식): 동기화, OCR, 분류, 캘린더, 검색, 미리보기, 로컬 전용, 읽기 전용 등. 이후 안드로이드/다중 캘린더 요구로 Req 18–19 추가 | `.kiro/specs/album-mcp/requirements.md` |
| 기술 검증 | 셸 실행 | osxphotos로 Photos 접근 시도 → 전체 디스크 접근 권한 문제 발견, 폴더 소스를 대안으로 설계. ocrmac이 한국어를 지원하지 않는 것을 확인하고 pyobjc로 Vision을 직접 호출(장당 0.5–1.3초) | `ocr.py`, `sources.py` |
| SDK 대응 | 셸 + 소스 읽기 | 설치된 mcp 2.3.0에서 FastMCP가 MCPServer로 바뀐 것을 패키지 소스에서 확인하고 새 API로 작성 | `server.py` |
| 구현 | 에이전트 코딩 | DB(마이그레이션, 백업 복원), 검색(한국어 OCR 띄어쓰기 보정), 캘린더 3종(AppleScript, Google API, RFC 5545 .ics), 썸네일 그리드 | `src/album_mcp/*` |
| 테스트 | 셸 실행 | 합성 이미지로 동기화, OCR, 검증, 검색 순위, .ics 생성, 중복 방지, 마이그레이션 테스트 | `tests/test_core.py` (8 passed) |
| MCP 연동 | MCP 설정 | 워크스페이스 `mcp.json`에 `rollcall` 서버 등록, MCP 클라이언트로 도구 9개 목록과 실제 스크린샷 동기화 확인 | `.kiro/settings/mcp.json` |
| AI 사용 규칙 | Steering | 분류 기준표, 3가지 워크플로(분류, 캘린더, 찾기), 상대 날짜는 캡쳐 시각 기준으로 해석, 검색어 한·영 확장 규칙 | `.kiro/steering/rollcall.md` |
| 자동화 | Hook | 세션 시작 시 새 캡쳐를 OCR 인덱싱하고, 미분류가 있으면 에이전트에게 알림 | `.kiro/hooks/rollcall-sync-on-start.json` |
| 완전 자동 | Kiro CLI 헤드리스 | launchd가 스크린샷 폴더를 감시 → `kiro-cli chat --no-interactive --trust-tools=@rollcall/...`로 분류와 등록. 처음엔 `@rollcall` 패턴이 승인되지 않아 도구별로 명시해 해결 | `cli.py` (`process`, `install-agent`) |
| 문서 | 에이전트 작성 | README, 이 보고서, 발표자료 | `README.md`, `BUILD_REPORT.md`, `PRESENTATION.pdf` |

## 설계 결정

| 결정 | 고른 것 | 대안 | 이유 |
|---|---|---|---|
| 의미 이해 | MCP를 쓰는 AI(Kiro)가 직접 분류·요약·태그 | Twelve Labs, 외부 비전 API, 임베딩 | Twelve Labs는 영상용. 외부 API는 사진이 Mac 밖으로 나가고 키 관리가 필요. 이미 대화 중인 AI가 OCR과 썸네일을 보는 편이 단순하고 정확 |
| 검색 | 필드 가중치 키워드 + AI의 질의 확장 + 썸네일로 최종 선택 | 벡터 DB (Chroma, Pinecone) | 분류 시 AI가 한·영 태그를 붙이므로 키워드로 충분. 의존성과 모델 다운로드 없음, 2초 이내 응답 |
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
