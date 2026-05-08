---
skill_name: shipoftheseus:theseus-orchestrator
skill_version: 0.9.38
phase: 04-nfr-verifications
project_id: etago
fingerprint: etago-04-nfr-v1
prev_fingerprint: etago-04-runtime-v1
produced_at: 2026-05-09
---

# Phase 04 — NFR-derived Verifications

§i 의 4 NFR 후보별 verification 합의.

| NFR | 검증 방법 | fail 처리 |
|-----|---------|---------|
| NFR-1 (auth-free) | `grep -nE 'os.Getenv|API_KEY|TOKEN|cookie' ./{cmd,internal} | wc -l == 0` | truthful record (자동 fix 금지 — 정책 위반 명시) |
| NFR-2 (priority-fidelity / 원문 보존) | unit test: 입력 "강남역" → outbound query string 디코드 시 "강남역" 등치 | auto-fix (escape 누락 시) |
| NFR-3 (minimal-extraction) | 응답 schema 단언 — output 구조체 = `{Start, End, DurationMin, Source}` 4 필드만 | truthful record |
| NFR-4 (usability) | `./etago --help` exit 0 + 텍스트 length ≥ 100 | auto-fix |

본 4 NFR 은 페이즈 09 의 derived gate 6 으로 자동 확장.
