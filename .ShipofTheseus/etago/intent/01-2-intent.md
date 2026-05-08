---
skill_name: shipoftheseus:theseus-orchestrator
skill_version: 0.9.38
phase: 01-2-intent-refresh1
project_id: etago
fingerprint: etago-01-2-v1
prev_fingerprint: etago-01-1-v1
produced_at: 2026-05-09
perspective: domain-axis
---

# Refresh-1 — Domain Axis

post-interview 한국 지도 도메인 시점.

- Naver 우선 — Naver 의 web `https://map.naver.com/p/api/directions/...` 또는 `https://map.naver.com/v5/api/dir/...` 류가 anonymously 접근 가능. 응답 JSON 의 `summary.duration` (ms) 또는 `total_time` (s).
- Kakao fallback — `https://map.kakao.com/route/?ep=...&sp=...` 또는 `https://map.kakao.com/api/dapi/v2/...` (인증 없는 web frontend XHR).
- 자연어 → 좌표: Naver `instant-search` / Kakao `dapi` 의 검색 API. 인증 없는 web flow 의무.
- 한국 도메인 특수: 전화번호/IC명/도로명/지명 모두 검색 가능. 좌표만 거부.

## 변화점 (refresh-1)

- 사용자가 Naver 우선을 선택해 *Naver schema reverse-engineering* 이 본 프로젝트의 핵심 기술 부담. plan 에서 schema 안정성 차원 (≥ 90% 응답 호환) 추가.
