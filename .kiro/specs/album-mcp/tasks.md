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
  - [ ] 14.1 Kiro에 전체 디스크 접근 권한을 주고 Photos 소스로 실제 스크린샷 동기화 확인
    - _Requirements: 1.1, 1.3, 1.5, 4.1_
  - [ ] 14.2 `apple` 백엔드로 실제 일정 1건 등록: "Rollcall" 캘린더 자동 생성, 자동화 권한 팝업, 장소·메모 확인
    - _Requirements: 6.8, 6.9, 19.1_
  - [ ] 14.3 `google` 백엔드 실제 계정 등록 확인 (OAuth 클라이언트 준비 시)
    - _Requirements: 19.1, 19.2_
  - [ ] 14.4 실제 스크린샷 전체(약 210장) 인덱싱 시간과 검색 응답 시간 측정
    - _Requirements: 7.10_
  - [ ] 14.5 `install-agent` 설치 후 새 스크린샷 1장 → 자동 분류·일정 등록까지 확인하고 해제
    - _Requirements: 17.7_

- [ ] 15. 데모
  - [ ] 15.1 시연 시나리오 녹화: 밋업 초대장 캡쳐 → 캘린더 등록, "지난번 캡쳐한 영수증 찾아줘" → 그리드 → 원본
  - [ ] 15.2 영상을 YouTube(일부 공개) 또는 Drive에 올리고 README Demo 줄에 링크

- [ ] 16. README 마무리 (제출 템플릿 섹션 맞추기)
  - [ ] 16.1 문제 정의에 대상 사용자, 근거(숫자·출처), 목표 추가
  - [ ] 16.2 핵심 기능 표에 "해결하는 불편"과 "코드 위치" 열 추가
  - [ ] 16.3 기대 효과를 숫자와 단위로 (14.4 측정값 사용)
  - [ ] 16.4 "테스트" 섹션 추가, 팀 섹션에 팀 번호·팀명·역할 표

- [ ] 17. 남은 작은 개선
  - [ ] 17.1 export 시 같은 이름 파일이 있으면 숫자 접미사로 저장 (현재 덮어씀)
    - _Requirements: 10.7_
  - [ ] 17.2 steering에 도구별 실패 처리(retry/skip/abort) 추가
    - _Requirements: 16.2_

- [ ] 18. 제출
  - [ ] 18.1 BUILD_REPORT 최종 확인, PRESENTATION.pdf에 데모 결과 반영
  - [ ] 18.2 18:00 전 push, 시크릿 창에서 레포 공개 확인, 제출 폼 입력
