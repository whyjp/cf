---
skill_name: shipoftheseus:theseus-orchestrator
skill_version: 0.9.38
phase: 06-plan-universe-2-meta
project_id: etago
fingerprint: etago-u2-meta-v1
prev_fingerprint: etago-u1-cold-v1
produced_at: 2026-05-09
universe_id: 2
seed: "Naver+Kakao race, first-success wins"
---

# Universe 2 — Concurrent Race

## Seed

`go func()` 두 개 동시 호출 → 첫 성공 결과 채택 (`select`). 평균 latency 더 낮음.

## 6-dim 점수

| 차원 | 점수 | 근거 |
|------|------|------|
| intent fidelity | 0.85 | 의도 §a "Naver 우선" 사용자 답과 misfit (race 는 우선 무관) |
| correctness | 0.90 | race 의 결과 비결정성 — 같은 입력에 다른 source |
| simplicity | 0.85 | goroutine + cancel + select |
| extensibility | 0.75 | 새 provider 추가 시 race 폭 ↑ |
| observability | 0.85 | which won 은 stderr 로 표시 가능, 단 시점마다 다름 |
| testability | 0.85 | 동시성 테스트 부담 |

평균 0.84.

## 차이집합 vs U1 (≥20 diff lines 의무)

1. `route.GetDuration` 본체가 sequential vs concurrent.
2. `time.Now` 측정 → 두 source 의 latency 비교 가능.
3. 첫 성공 결과 후 나머지 cancel.
4. Source 결정이 *런타임 race* 결과 — 사용자가 동일 입력에 다른 source 받음.
5. C3 임계: per-source 6s 가 아닌 *whichever wins first* — 평균 더 좋음.
6. 네트워크 비용 2배 — 호출자의 rate-limit 부담 ↑ (Q-N7 가드 0 정책과 충돌).
7. fallback trigger 룰이 무의미 — 둘 다 동시에 시도하므로.
8. 의존: `sync` package 추가 사용.
9. 테스트: 동시성 race condition test 의무.
10. 실패 케이스: *둘 다 실패* 까지 timeout 6s + 6s 가 아닌 max(6s,6s)=6s — 약간의 latency 절감.
11. observability: `Source` 필드만으론 *의도된 우선* 인지 *race winner* 인지 cold reader 모호.
12. 의도 §c (비목표) 와 misfit — "추천 루트 시간" 단일성 ≠ "더 빠른 source 의 시간".
13. UX: 사용자 의도와 다른 source 결과 경고 stderr 의무.
14. resource: 두 goroutine + ctx cancel 동기화.
15. 코드 라인 수: U1 보다 ~20% 더 많음.
16. 보안: 차단 IP risk 도 2배 (두 endpoint 동시 hit).
17. 디버깅: 응답 비결정 → bug 재현 어려움.
18. determinism: 0 — 같은 입력에 다른 결과 가능.
19. 의존성: `golang.org/x/sync/errgroup` 후보 (외부 dep DEC-6 위반).
20. handoff: race semantics 추가 설명 필요.
21. SOLID: `route.GetDuration` 의 책임이 라우팅 + 동시성으로 분산.

## Tournament 예측

intent fidelity 가 *결정타* — 사용자 명시 "Naver 우선 + Kakao fallback" 룰과 misfit. U1 우세.
