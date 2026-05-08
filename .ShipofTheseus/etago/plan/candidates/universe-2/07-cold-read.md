---
skill_name: shipoftheseus:theseus-orchestrator
skill_version: 0.9.38
phase: 06-plan-universe-2-cold-read
project_id: etago
fingerprint: etago-u2-cold-v1
prev_fingerprint: etago-u2-plan-v1
produced_at: 2026-05-09
---

# Universe 2 — Cold Read

- 명료성: 0.85 — 동시성 코드 cold-read 부담.
- 위험: 의도 §a (Naver 우선) 와 misfit. determinism 0.
- 결함: race 결과 비결정성 → 같은 입력에 source 다를 수 있음.
