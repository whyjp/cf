---
skill_name: shipoftheseus:theseus-orchestrator
skill_version: 0.9.38
phase: 06-plan-universe-1-meta
project_id: etago
fingerprint: etago-u1-meta-v1
prev_fingerprint: etago-05-refreshed-v1
produced_at: 2026-05-09
universe_id: 1
seed: "Naver-first sequential, Kakao-fallback"
---

# Universe 1 — Naver-first sequential

## Seed

`Try Naver → if fail, try Kakao` 단순 sync 체인. 가장 KISS.

## 6-dim 점수 (자체 평가)

| 차원 | 점수 | 근거 |
|------|------|------|
| intent fidelity | 0.97 | 의도 §a 정확 — "추천 루트 시간만" |
| correctness | 0.95 | 단순 → 버그 적음 |
| simplicity | 0.98 | 가장 단순 |
| extensibility | 0.70 | 새 provider 추가 시 코드 분기 의무 |
| observability | 0.90 | which source 사용했는지 명료 (stderr) |
| testability | 0.95 | mock 분리 명료 |

평균 0.91.

## 차이집합 vs U2

- U1: sequential, U2: concurrent
- U2 는 평균 latency 더 낮지만 의도 §a "추천 루트 시간" 단일성에 race-winner 가 *어느 source* 인지 불명확
- U1 은 결정론적 — 항상 Naver 우선

## 차이집합 vs U3

- U1: 직접 함수 호출, U3: 인터페이스 + 플러그인
- 본 작업의 provider = 2개. 인터페이스는 over-engineering
