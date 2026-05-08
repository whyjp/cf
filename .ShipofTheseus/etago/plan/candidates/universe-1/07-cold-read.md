---
skill_name: shipoftheseus:theseus-orchestrator
skill_version: 0.9.38
phase: 06-plan-universe-1-cold-read
project_id: etago
fingerprint: etago-u1-cold-v1
prev_fingerprint: etago-u1-plan-v1
produced_at: 2026-05-09
---

# Universe 1 — Cold Read

cold reader 가 본 plan 만 보고 재이해.

- 명료성: 0.95 — 8 항목 모두 채워짐, sequenceDiagram 4개로 모듈 흐름 명확.
- 위험: Naver/Kakao 의 *비공식 web endpoint* 의존 — implementer 가 실 호출로 검증 의무. plan 8.T-003/T-004 에 *후보 필드* 명시 + "implementer 가 정정" 명시.
- 결함: 0.

진입 OK.
