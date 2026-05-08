---
skill_name: shipoftheseus:theseus-orchestrator
skill_version: 0.9.38
phase: 00-naming
project_id: etago
fingerprint: etago-00-naming-v1
prev_fingerprint: pending-00-cand-v1
produced_at: 2026-05-09
user_explicit_confirmation: true
---

# Phase 00 — etago 확정

## 프로젝트명

**`etago`** — ETA + Go. 사용자 명시 선택. 충돌 검사: npm/PyPI/GitHub 동명 무관 단일 repo만, 의미 충돌 0.

## 모듈명 (1차)

| 모듈 | 책임 | 정당화 |
|------|------|--------|
| `cmd/etago` | CLI 진입점 (cobra/표준 flag) — `etago "강남" "수원"` | Go convention `cmd/<binary>` |
| `internal/parse` | 자연어 start/end 파싱 + 정규화 | input layer |
| `internal/route` | map service adapter (Naver/Kakao 웹 라우트 fetch) | external adapter |
| `internal/duration` | 응답 → 분/시간 단위 시간값 추출 | output layer |

## 즉시 사용 가능 식별자

- 폴더: `etago/`, `cmd/etago/`, `internal/{parse,route,duration}/`
- Go 모듈 path: `github.com/<user>/etago` (사용자 confirm 시 확정 — 페이즈 04 후속)
- 바이너리: `etago(.exe)`

## 정당화 한 줄

CLI 호출 친화 + 산출물 (ETA) + 언어 (Go) 의미 명료, 기존 OSS 충돌 0.
