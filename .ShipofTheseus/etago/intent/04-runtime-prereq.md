---
skill_name: shipoftheseus:theseus-orchestrator
skill_version: 0.9.38
phase: 04-runtime-prereq
project_id: etago
fingerprint: etago-04-runtime-v1
prev_fingerprint: etago-04-verify-v1
produced_at: 2026-05-09
qd9_answer: 4
entry_blocked: false
---

# Phase 04 — Runtime Prerequisite (Q-D9 답: 4 = 외부 의존 0)

## 분류

| 항목 | 필요? | 비고 |
|------|------|------|
| API key | ❌ | 의도 §d C1 — 토큰 0 |
| .env file | ❌ | `.env.template` 비어 있음 / 미생성 OK |
| 외부 서비스 | ⚠️ Naver/Kakao 공개 endpoint | 익명 접근 OK. 서비스 down 시 fallback. 본 prereq 의 분류상 *runtime dep* (env-bound 아님) |
| 시스템 패키지 (런타임) | ❌ | Go binary self-contained |
| **Go 툴체인 (빌드 시)** | ⚠️ 1.22+ | **현재 환경 미설치 검출** — 페이즈 09 smoke (`go build`) 부분 강등 (사용자 manual). 산출 소스 코드는 syntax-correct 의무. |
| 포트 | ❌ | CLI — 서버 0 |
| 네트워크 | ✅ outbound HTTPS 443 | 방화벽 / corp proxy 환경 시 사용자 책임 |

## .env.template

비어 있음. (`.env` 파일 자체 미생성)

## Mock 모드

```bash
# offline 환경 단위 테스트
go test -short ./...   # network skip
```

## 페이즈 09 게이트 입력

게이트 7 (env-satisfied + 실 실행 1회) 는 본 답 (4) 으로 *env 검증 0* + *실 실행 1회* 만 의무. → `etago "강남역" "수원시청"` 가 실 네트워크 호출 + exit 0 검증.
