# Implementation Plan

> 이 할 일 목록은 구현을 먼저 진행한 뒤 실제 커밋 기록을 기준으로 정리했습니다. `[x]`는 코드와 테스트(또는 수동 검증)가 있는 작업, `[ ]`는 남은 작업입니다. 요구사항 번호는 `requirements.md` 기준이며, 범위에서 뺀 기준은 그 문서에 **[이번 범위 제외]**로 표시했습니다.

- [x] 1. 프로젝트 골격과 기술 검증
  - uv 프로젝트(Python 3.12), 의존성: `mcp` 2.x, osxphotos, pyobjc Vision/Quartz, Pillow, pillow-heif, Google 선택 의존성
  - osxphotos로 Photos 접근 시도 → 전체 디스크 접근 권한 없이는 열리지 않음을 확인, 폴더 소스를 대안으로 결정
  - ocrmac이 한국어를 허용하지 않음을 확인 → Vision을 pyobjc로 직접 호출하기로 결정
  - 설치된 `mcp` 2.3.0에서 FastMCP가 `MCPServer`로 바뀐 것을 확인
  - _Requirements: 3.1, 15.3_

- [x] 2. 온디바이스 OCR (`ocr.py`)
  - Apple Vision, ko-KR + en-US, accurate, 위→아래 정렬, 줄바꿈 보존
  - 실패 시 빈 문자열 반환과 로그
  - _Requirements: 3.1, 3.2, 3.3, 11.4_

- [x] 3. 로컬 DB와 마이그레이션 (`db.py`)
  - captures, events, state 테이블, `PRAGMA user_version` 버전 관리
  - 마이그레이션 전 백업, 실패 시 복원
  - 분류 검증(kind 4종, summary ≤ 200자), 재분류 시 덮어쓰기
  - _Requirements: 2.1, 2.4, 2.5, 2.6, 5.1, 5.2, 5.3, 5.5, 5.7, 5.8, 11.2, 13.1_

- [x] 4. 캡쳐 소스 (`sources.py`)
  - [x] 4.1 Photos 소스: 스크린샷만, iCloud 전용이면 Local_Preview 사용, Apple 라벨, 권한 오류 안내
    - _Requirements: 1.3, 1.5, 4.1, 4.2, 12.1, 12.2, 14.4, 18.5_
  - [x] 4.2 폴더 소스: 여러 폴더, png/jpg/jpeg/heic/webp, mtime을 생성 시각으로, 소스별 id 접두사
    - _Requirements: 18.1, 18.2, 18.3, 18.6_

- [x] 5. 동기화와 inbox (`core.py`)
  - watermark 기반 증분 동기화, 호출당 `limit`개 OCR 후 `remaining` 반환, 중복 없음
  - inbox: 미분류를 오래된 순으로
  - _Requirements: 1.1, 1.6, 1.7, 1.8, 2.1, 2.6_

- [x] 6. 검색 (`search.py`)
  - 필드 가중치, 한국어 OCR 띄어쓰기 보정, 여러 검색어 일치 가산, kind·기간 필터, 최대 50개
  - _Requirements: 7.2, 7.4, 7.6, 7.7, 7.8, 7.13_

- [x] 7. 미리보기와 사진 꺼내기 (`preview.py`, `core.py`)
  - 번호 썸네일 그리드(4열, 400px), 번호↔id 범례, 없는 id 건너뛰기
  - get_photo: JPEG q90 + 메타데이터, export_photos: 복사, 폴더 생성
  - _Requirements: 8.2, 8.3, 8.4, 8.6, 8.7, 8.8, 9.2, 9.3, 9.4, 10.4, 10.8, 10.10_

- [x] 8. 캘린더 백엔드 (`calendars.py`)
  - [x] 8.1 일정 검증: 제목 필수, ISO 날짜/일시, start ≤ end, end 생략 시 +1시간, 메모에 capture id
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7_
  - [x] 8.2 Apple Calendar(AppleScript, 인자로 값 전달, 캘린더 자동 생성, 권한 오류 안내)
    - _Requirements: 6.8, 6.9, 19.1_
  - [x] 8.3 Google Calendar API(OAuth, 토큰 레포 밖 0600)
    - _Requirements: 19.1, 19.2_
  - [x] 8.4 .ics(RFC 5545, UTC 시각)와 중복 등록 방지
    - _Requirements: 19.1, 19.3, 19.4_

- [x] 9. MCP 서버 (`server.py`)
  - 도구 9개, 요청 id 로깅(stderr), 오류를 `ErrorType: message`로 반환
  - 병렬 호출 시 SQLite 공유 연결 충돌 → 락으로 직렬화 (병렬 10개 호출 오류 0 확인)
  - _Requirements: 11.5, 14.1, 14.2, 14.3_

- [x] 10. Kiro 설정과 steering
  - `.kiro/settings/mcp.json`에 `rollcall` 서버, 쓰기 도구는 사용자 승인
  - `.kiro/steering/rollcall.md`: 분류 기준표, 3개 워크플로, 예시
  - _Requirements: 15.1, 15.3, 16.1, 16.3, 16.4, 16.5, 16.6_

- [x] 11. 자동 처리 (`cli.py`, hook)
  - [x] 11.1 SessionStart hook: OCR 인덱싱 후 미분류 개수 알림
    - _Requirements: 17.1, 17.4_
  - [x] 11.2 `album-mcp process`: Kiro CLI 헤드리스로 분류·일정 등록 (rollcall 도구만 신뢰)
    - _Requirements: 17.2, 17.6_
  - [x] 11.3 `album-mcp install-agent`: launchd WatchPaths + 30분 간격
    - _Requirements: 17.7_

- [x] 12. 테스트
  - `tests/test_core.py` 8개 통과 (합성 이미지 + folder 소스 + ics 백엔드)
  - MCP 클라이언트로 도구 목록·실제 스크린샷 동기화 확인
  - 엔드투엔드: 합성 밋업 초대장·영수증으로 `album-mcp process` → event/reference 분류, 밋업 일정 .ics 생성
  - _Requirements: 1.1, 5.2, 5.3, 6.4, 7.6, 7.7, 8.6, 10.8, 13.1, 19.3, 19.4_

- [x] 13. 문서 초안
  - README(문제 정의, 기능, 시나리오, 설치, 설정, 안드로이드, 캘린더 선택), BUILD_REPORT, PRESENTATION.pdf 초안
  - _Requirements: 15.2, 15.4, 18.4_

- [ ] 14. 실제 환경 검증
  - [x] 14.1 전체 디스크 접근 권한을 준 뒤 Photos 소스로 실제 동기화: 보관함 42,147장(스크린샷 21,464장) 로딩 7.6초, MCP `sync_captures(limit=20)`로 최근 캡쳐 20장 색인, inbox 30장 분류(event 1, insight 9, reference 10, other 10). 이어서 최근 30일 나머지 72장도 색인·분류(누적 102장: event 8, insight 30, reference 32, other 32). 일정은 사용자 확인 후 1건 등록(아이언트 대금 11/13 종일), 나머지 일정 후보 7건은 확인 대기
    - _Requirements: 1.1, 1.3, 1.5, 4.1_
  - [x] 14.2 `apple` 백엔드로 실제 일정 등록: "Rollcall" 캘린더 자동 생성, Calendar에서 다시 읽어 제목·시각(19:00–21:00)·장소·메모(capture id, 경로) 확인
    - _Requirements: 6.8, 6.9, 19.1_
  - [ ] 14.3 `google` 백엔드 실제 계정 등록 확인 (OAuth 클라이언트 준비 시)
    - _Requirements: 19.1, 19.2_
  - [x] 14.4 실제 스크린샷 211장 측정: 인덱싱 44초(장당 0.21초), 검색 4–5ms. OCR 텍스트 20자 초과 130장, 2×2px 이미지 1장은 OCR 실패로 빈 문자열 저장 (5만 장 규모는 미측정)
    - _Requirements: 7.10_
  - [x] 14.5 `install-agent` 설치 → 감시 폴더에 예약 확인 캡쳐 1장 추가 → 약 90초 뒤 사람 조작 없이 event로 분류되고 Apple Calendar에 "을지로 00식당 예약 (4명)" 11/21 18:30 등록 확인 → 해제
    - _Requirements: 17.7_

- [x] 19. sync 기본값을 "최근 30일, 최신순"으로 변경
  - watermark 대신 `days`(기본 30) 창 안에서 미색인 캡쳐를 최신순으로 처리. `since`로 더 과거 지정 가능. MCP 도구와 CLI(`--days`) 모두
  - 이유: Photos를 처음 열자 2017년 캡쳐부터 색인을 시작함
  - _Requirements: 1.1, 1.8_

- [x] 20. 일반 사진 찾기 `find_photos(labels, since, until, limit=40)`
  - 보관함 전체(스크린샷 아닌 사진 포함)를 Apple 라벨(대소문자 무시, 하나라도 일치)과 날짜로 거름, 최신순, OCR·색인 없음
  - PhotosDB와 사진 목록은 프로세스당 한 번 읽어 메모리에 둠
  - 반환한 `photos:<uuid>` id를 `look_at`, `get_photo`, `export_photos`에서 그대로 사용
  - steering "찾기" 절차에 캡쳐에서 못 찾으면 `find_photos` → `look_at`으로 직접 보고 고르는 단계 추가
  - 테스트: 가짜 PhotosDB로 라벨·날짜 필터, 최신순, limit, look_at/get_photo/export (`test_find_photos_whole_library_and_reuse_ids`)
  - 실제 검증: "차 사고 난 내 차 사진" → `search`는 관련 없는 2017년 캡쳐 1건 → `find_photos(["Bumper"])` 129장 → `look_at` 그리드 9장 중 3장을 보고 파손 사진 14장 선택 (2024-07-03 뒷범퍼 찌그러짐 9장, 2024-11-08~11 뒷범퍼 옆 들뜸 5장)
  - _Requirements: 7.1, 7.3, 8.6, 9.1, 10.1_

- [x] 21. 남은 개선
  - [x] 21.1 오래 켜진 서버도 새 사진을 보도록 사진 목록을 5분(`ALBUM_MCP_PHOTOS_REFRESH`)마다 다시 읽음. 테스트 `test_photos_cache_refreshes`
  - [x] 21.2 `look_at`이 없는 파일을 건너뛰면 번호가 입력 순서와 달라짐 (실제 검증 중 발생). 번호↔id 범례로 읽도록 steering에 명시

- [ ] 15. 데모
  - [ ] 15.1 시연 시나리오 녹화: 밋업 초대장 캡쳐 → 캘린더 등록, "지난번 캡쳐한 영수증 찾아줘" → 그리드 → 원본
  - [ ] 15.2 영상을 YouTube(일부 공개) 또는 Drive에 올리고 README Demo 줄에 링크

- [x] 16. README 마무리 (제출 템플릿 섹션 맞추기)
  - [x] 16.1 문제 정의에 대상 사용자, 기존 방식과 한계, 근거(실측 211장), 목표 추가
  - [x] 16.2 핵심 기능 표에 "해결하는 불편"과 "코드 위치" 열 추가
  - [x] 16.3 기대 효과를 숫자와 단위로 (14.4 측정값 사용)
  - [x] 16.4 "테스트" 섹션 추가, 팀 섹션에 팀 번호·팀명·역할 표

- [x] 17. 남은 작은 개선
  - [x] 17.1 export 시 같은 이름 파일이 있으면 숫자 접미사(`_1`)로 저장, 테스트 추가
    - _Requirements: 10.7_
  - [x] 17.2 steering에 도구별 실패 처리(retry/skip/abort) 표 추가
    - _Requirements: 16.2_

- [ ] 18. 제출
  - [ ] 18.1 BUILD_REPORT 최종 확인, PRESENTATION.pdf에 데모 결과 반영
    - [x] 실제 보관함 결과 슬라이드 추가(42,147장, 분류 30건, 차 파손 사진 129 → 14장), 수치 갱신. 번호판이 보이는 실제 차 사진은 공개 PDF에 넣지 않음
    - [ ] 데모 영상 링크 반영 (15 이후)
  - [ ] 18.2 18:00 전 push, 시크릿 창에서 레포 공개 확인, 제출 폼 입력
