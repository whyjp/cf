---
skill_name: shipoftheseus:theseus-orchestrator
skill_version: 0.9.38
phase: 04-autonomy
project_id: etago
fingerprint: etago-04-autonomy-v1
prev_fingerprint: etago-04-answers-v1
produced_at: 2026-05-09
---

# Phase 04 — 자율 대원 카탈로그 (Q-D1 ~ Q-D9)

| Q | 항목 | 답 | 의미 |
|---|------|------|------|
| Q-D1 | 회귀 권고 자동 적용 | 1 (자동 적용) | 페이즈 11 회귀 발견 시 즉시 정정 |
| Q-D2 | 경쟁 resolve 자동 적용 | 1 (자동) | tournament winner 자동 머지 |
| Q-D3 | 천정 도달 자동 임계 조정 | 1 (자동) | 임계 0.999 도달 후속 sprint 자율 |
| Q-D4 | 정체 누적 정책 | 1 (자동 lessons 적용) | sprint 정체 시 lesson 학습 |
| Q-D5 | 자율 패키지 업데이트 | 1 (자동) | go.mod/go.sum minor/patch 자동 |
| Q-D6 | 자율 결정 보고 빈도 | 3 (sprint 단위) | 페이즈별 frontmatter + 14-handoff 요약 |
| Q-D7 | 체크포인트 회귀 + 멀티버스 | 1 (자동, 단 회귀 0.05 임계) | G3 폭 3 |
| Q-D8 | Verification commands | 1 (실 네트워크 smoke) | 본 답으로 04-verification.md 채워짐 |
| Q-D9 | Runtime prereq | 4 (외부 의존 0 — map service 는 익명 공개) | `.env.template` 빈 OK, 페이즈 09 게이트는 *실 부팅* 검증 |

본 답이 사후 모든 자율 결정의 근거. self_lint C-AU 검증.
