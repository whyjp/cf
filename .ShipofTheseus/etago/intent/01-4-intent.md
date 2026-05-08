---
skill_name: shipoftheseus:theseus-orchestrator
skill_version: 0.9.38
phase: 01-4-intent-refresh1
project_id: etago
fingerprint: etago-01-4-v1
prev_fingerprint: etago-01-3-v1
produced_at: 2026-05-09
perspective: risk-axis
---

# Refresh-1 — Risk Axis

post-interview 리스크 시점.

| 리스크 | 가능성 | 완화 |
|--------|--------|------|
| Naver/Kakao 가 schema 변경 | 中 | adapter 패턴 + 테스트 fixture 정기 갱신 (사용자 운영 책임) |
| IP rate limit / 자동 차단 | 中 | UA 고정 + 호출자 책임 (Q-N7 답) |
| 자연어 모호 (강남 → 강남구/강남역) | 中 | first-match 자동 + stderr hint (Q-N3) |
| 네트워크 timeout / partial 응답 | 中 | 6s timeout + fallback 체인 |
| 개인정보 / 토큰 누출 | 0 | NFR-1 — auth-free 의무 |
| 한국 외 입력 | 低 | 비-목표 명시 (intent §c) |
| Windows 한글 콘솔 인코딩 | 中 | UTF-8 stdout 의무 + cp949 회피 (PowerShell `chcp 65001` 권장 README) |

## 변화점 (refresh-1)

- Windows 콘솔 한글 출력 케이스가 신규 식별 — handoff 에 README 명시 의무.
