---
skill_name: shipoftheseus:theseus-orchestrator
skill_version: 0.9.38
phase: 06-plan-universe-3-meta
project_id: etago
fingerprint: etago-u3-meta-v1
prev_fingerprint: etago-u2-cold-v1
produced_at: 2026-05-09
universe_id: 3
seed: "Router + plug-in providers (extensible)"
---

# Universe 3 — Router + Plug-in

## Seed

`Provider` 인터페이스 + 등록 레지스트리. 새 provider (TMAP / OSRM / Google) 추가 시 코드 분기 0.

## 6-dim 점수

| 차원 | 점수 | 근거 |
|------|------|------|
| intent fidelity | 0.85 | extensibility 가 비목표 (intent §c 명시 0 — 새 provider 의도 0) |
| correctness | 0.92 | 인터페이스 분리 → 단위 테스트 용이 |
| simplicity | 0.75 | YAGNI — provider 2개에 router 인프라 over-engineering |
| extensibility | 0.98 | 새 provider 의 코드 분기 0 |
| observability | 0.90 | 각 provider hit 기록 |
| testability | 0.93 | 인터페이스 mock 용이 |

평균 0.89.

## 차이집합 vs U1 (≥20 diff lines)

1. `Provider` 인터페이스 + 레지스트리.
2. `Router` 구조체가 fallback 정책 캡슐화.
3. `init()` 함수에서 자동 register.
4. 새 file `internal/route/registry.go`.
5. provider 별 priority weight 설정.
6. config 파일 가능성 (yaml/json) — 다만 의도 §d (no-token) 가드.
7. interface 분리 → mock 작성 trivial.
8. 코드 라인 수: U1 보다 ~50% 더 많음.
9. 의도 §c "추천 루트 시간만" 단일 책임 vs router infrastructure overhead.
10. SOLID OCP 충실 vs YAGNI 위반.
11. handoff 복잡도 ↑ — provider 추가 방법 문서 의무.
12. 단위 테스트 수 ~2배.
13. 컴파일 시간 ↑.
14. binary 크기 ↑ (interface vtable).
15. cold-read 부담 ↑.
16. 새 dep 가능성 (의존성 주입 lib) — 단 stdlib only 으로 가능.
17. provider 2개에 router 인프라 — 비용 vs 가치 mismatch.
18. 의도 §h Q-N1 답 (Naver 우선) 가 router policy 로 흡수되지만 *명시적이지 않음*.
19. error handling: provider 별 분기 vs router 단일 정책 — debugging 부담 ↑.
20. test surface: provider interface conformance test 의무.
21. observability: provider 별 metrics — over-instrumentation.

## Tournament 예측

simplicity 차원에서 U1 에 패배. extensibility 우위 하지만 *비목표*.
