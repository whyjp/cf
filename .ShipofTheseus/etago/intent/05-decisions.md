---
skill_name: shipoftheseus:theseus-orchestrator
skill_version: 0.9.38
phase: 05-decisions
project_id: etago
fingerprint: etago-05-dec-v1
prev_fingerprint: etago-05-crit-v1
produced_at: 2026-05-09
---

# Phase 05 — Decisions

비평 결과 → 페이즈 06 plan 전 자율 결정 카탈로그.

| ID | 결정 | 근거 |
|----|------|------|
| DEC-1 | intent §c 6→5 항 (톨게이트비 제거) | review L-1 + critique a |
| DEC-2 | C3 임계 보강 (`per-source ≤ 6s`, `total ≤ 12s`) | critique b |
| DEC-3 | exit code 매트릭스 plan 의무 | D-6 + critique c |
| DEC-4 | fallback trigger 룰 plan 의무 | D-4 + critique c |
| DEC-5 | universe 3 seed = "router + plug-in providers" | critique 분기 후보 |
| DEC-6 | dependency 추가 정책: stdlib only default (반드시 plan 에 정당화) | refresh-1 tech-axis |
| DEC-7 | Windows README cp949 hint 의무 | refresh-1 risk-axis |
| DEC-8 | NFR-2 verification 에 percent-encoding 룰 명시 | refresh-1 additional d |
