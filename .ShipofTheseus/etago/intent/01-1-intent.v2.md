---
skill_name: shipoftheseus:theseus-orchestrator
skill_version: 0.9.38
phase: 01-1-intent-refresh2
project_id: etago
fingerprint: etago-01-1-v2
prev_fingerprint: etago-05-dec-v1
produced_at: 2026-05-09
perspective: user-axis
---

# Refresh-2 — User Axis (post-critique)

DEC-3 (exit code 매트릭스) 반영:
- 0 = 정상
- 1 = 알 수 없는 내부 오류
- 2 = 입력 오류 (자연어 매칭 0 / 좌표 거부)
- 3 = 외부 실패 (Naver+Kakao 모두 실패)

DEC-7 (Windows README) — cp949/PowerShell 케이스 README 의무로 반영. 사용자 cold-read 가능.
