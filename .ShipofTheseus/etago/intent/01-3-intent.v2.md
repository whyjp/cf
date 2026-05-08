---
skill_name: shipoftheseus:theseus-orchestrator
skill_version: 0.9.38
phase: 01-3-intent-refresh2
project_id: etago
fingerprint: etago-01-3-v2
prev_fingerprint: etago-01-2-v2
produced_at: 2026-05-09
perspective: tech-axis
---

# Refresh-2 — Tech Axis (post-critique)

DEC-6 (의존 정책): stdlib-only default. 외부 라이브러리 추가는 plan 에 정당화 의무 — 본 작업에서는 *불필요* 으로 결정 (universe 1/2 모두 stdlib).

DEC-2 (C3 보강): per-source 6s + total 12s. `context.WithTimeout(ctx, 6*time.Second)` 두 번. fallback 합산 별도 cap.
