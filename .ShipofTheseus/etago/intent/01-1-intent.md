---
skill_name: shipoftheseus:theseus-orchestrator
skill_version: 0.9.38
phase: 01-1-intent-refresh1
project_id: etago
fingerprint: etago-01-1-v1
prev_fingerprint: etago-04-audience-v1
produced_at: 2026-05-09
perspective: user-axis
---

# Refresh-1 — User Axis

post-interview 사용자 행동 시점.

- 사용자 = 봇/cron 작성자. 호출 패턴: `etago "<start>" "<end>"` 단발 → 분 정수 파싱 → 후속 로직 (알림/스케줄).
- 자연어 변화: "강남" / "강남역" / "강남구청" — 모두 다른 결과. *원문 우선* 룰이 사용자가 의도한 정확도 보존.
- 실패 처리: 사용자는 exit code 로 분기. 0 = 정상, 비-0 = 알림 retry / fallback 알림.

## 변화점 (refresh-1)

- "max-autonomy" 답으로 사용자 명시 인터럽트 0 — implementation 의 모든 default 가 *사후 사용자 설명 가능* 해야 함. 페이즈 14 handoff 가 이를 풀 매핑.
