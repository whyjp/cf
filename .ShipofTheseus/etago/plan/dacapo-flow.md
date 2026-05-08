---
skill_name: shipoftheseus:theseus-orchestrator
skill_version: 0.9.38
phase: 06-dacapo-flow
project_id: etago
fingerprint: etago-dacapo-flow-v1
prev_fingerprint: etago-dacapo-01-v1
produced_at: 2026-05-09
---

# Da Capo Flow — Plan 페이즈

## Mermaid

```mermaid
sequenceDiagram
    participant Planner
    participant T as Tournament
    participant D as DaCapo
    participant C as Canonical 06-plan.md

    Planner->>T: 3 universes (U1/U2/U3)
    T->>T: 6-dim sub-scores
    T-->>Planner: Winner=U1 (avg 0.91)
    Planner->>D: lessons L-1, L-2
    D->>D: re-plan U1 with lessons
    D-->>Planner: U1 v2 (avg 0.945)
    Planner->>C: write canonical 06-plan.md
    C-->>Planner: ready for phase 07/08
```

## Timeline

| Step | 시각 | 산출 |
|------|------|------|
| A | 2026-05-09T00:02:00 | tournament-01.md |
| B | 2026-05-09T00:02:30 | dacapo-rerun-01.md |
| C | 2026-05-09T00:03:00 | canonical 06-plan.md |

## Step trace per round

Round 1 (1회만, G3 cap):
- F: lessons 추출 (cross-universe 차이집합 + tournament reasoning)
- G: U1 v2 re-plan (Provider 인터페이스 + Latency 필드)
- 검증: 6-dim 재채점 — 0.91 → 0.945
- 결정: round 종료 (G3 dacapo 1회 의무 충족)
