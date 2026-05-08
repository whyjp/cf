---
skill_name: shipoftheseus:theseus-orchestrator
skill_version: 0.9.38
phase: 08-tournament-impl-01
project_id: etago
fingerprint: etago-tour-impl-01-v1
prev_fingerprint: etago-impl-u1-meta-v1
produced_at: 2026-05-09
round: 1
---

# Tournament — Implementation Round 1

## 단일 universe 채택 근거

플랜 페이즈에서 `tournament-01` (3 universes) → U1 winner + dacapo 정밀화 완료. 페이즈 08 진입 시 *implementation 분기* 는 단일 universe (U1) 만 구현 — G3 의 plan-tree 폭 3 은 *플랜 단계* 에서 소진.

implementation 단계의 *내부 분기* 는 dacapo loop (페이즈 10 sprint) 가 담당.

## 6-dim sub-scores

| 차원 | U1 (구현) |
|------|:--:|
| intent | 0.97 |
| correctness | 0.95 |
| simplicity | 0.96 |
| extensibility | 0.85 |
| observability | 0.95 |
| testability | 0.97 |

평균 **0.94**.

## Cross-universe 차이집합 (vs 가상 U2/U3 impl)

| 차원 | U1 sequential | U2 race | U3 router |
|------|---|---|---|
| 코드 라인 (실측) | ~700 | ~830 (hypothetical) | ~1000 (hypothetical) |
| 외부 dep | 0 | 0 | 0 |
| 테스트 surface | 27 | ~35 (race condition) | ~40 (registry conformance) |
| 결정성 | 100% | 0% | 100% |
| Provider 추가 비용 | 코드 분기 + main.go 수정 | goroutine launch | Registry.Register |

U1 winner 는 plan 단계 결정과 일치. impl 에서 변경 사유 없음.

## Lessons (impl 단계)

- L-impl-1: Naver/Kakao web schema 가 *hard-coded* 가 아닌 *walk-for-pattern* (extractFirstCoord/walkForLatLng) 로 구현 — schema drift 에 robust.
- L-impl-2: Sentinel error (`ErrInputRejected`/`ErrUpstreamFail`/`ErrEmptyPath`) 분리 → exit code 매트릭스 명료.
- L-impl-3: `httptest` 기반 mock 으로 단위 테스트 — live endpoint 의존 0 단위 단계.

위 lessons 페이즈 10 sprint 에 polish input.
