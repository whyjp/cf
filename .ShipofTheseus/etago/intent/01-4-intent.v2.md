---
skill_name: shipoftheseus:theseus-orchestrator
skill_version: 0.9.38
phase: 01-4-intent-refresh2
project_id: etago
fingerprint: etago-01-4-v2
prev_fingerprint: etago-01-3-v2
produced_at: 2026-05-09
perspective: risk-axis
---

# Refresh-2 — Risk Axis (post-critique)

DEC-1 (톨게이트비 비목표 제거) — 사용자 의도와 무관, 잡음 제거.

신규 리스크 (critique premortem 추가):
- corp proxy 502 → error message 에 proxy hint
- Naver cookie+CSRF 강제 변경 → adapter 가 흡수 (1-GET set-cookie + 2-요청)
- Windows 한글 args 깨짐 → UTF-8 args 의무 + README

모두 plan 의 fallback policy 에 반영.
