---
skill_name: shipoftheseus:theseus-orchestrator
skill_version: 0.9.38
phase: 01-2-intent-refresh2
project_id: etago
fingerprint: etago-01-2-v2
prev_fingerprint: etago-01-1-v2
produced_at: 2026-05-09
perspective: domain-axis
---

# Refresh-2 — Domain Axis (post-critique)

DEC-4 (fallback trigger 룰):
- HTTP 5xx → fallback
- HTTP 4xx → input error (no fallback)
- HTTP 200 + empty path / duration=0 → fallback
- HTTP 200 + parse 실패 → fallback (단, 1회만 — 무한 루프 가드)
- timeout (per-source) → fallback

DEC-5 universe 3 seed 채택 — extensibility (router + plug-in providers) 검증 대상.
