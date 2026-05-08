---
skill_name: shipoftheseus:theseus-orchestrator
skill_version: 0.9.38
phase: 01-3-intent-refresh1
project_id: etago
fingerprint: etago-01-3-v1
prev_fingerprint: etago-01-2-v1
produced_at: 2026-05-09
perspective: tech-axis
---

# Refresh-1 — Tech Axis

post-interview 기술 시점.

- Go stdlib `net/http` + `encoding/json` 조합으로 zero-dep 가능.
- `context.WithTimeout(6s)` for per-source timeout.
- `flag` 표준 패키지 — 위치 인자 2개 + `--json --timeout --source --ua --help`.
- HTTP 호출 시 `Accept-Language: ko`, `User-Agent: Mozilla/5.0 ...` (Chrome stable) 고정.
- 한글 인코딩: Go string 은 UTF-8 native — query escape (`url.QueryEscape`) 만 거치면 된다.

## 변화점 (refresh-1)

- 의존 0 default 확정. 외부 라이브러리 추가 시 plan 에 정당화. Q-D5 max-autonomy 라도 dep 추가는 *plan 의무 항목* 으로 트랙.
