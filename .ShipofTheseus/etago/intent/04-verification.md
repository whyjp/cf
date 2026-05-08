---
skill_name: shipoftheseus:theseus-orchestrator
skill_version: 0.9.38
phase: 04-verification
project_id: etago
fingerprint: etago-04-verify-v1
prev_fingerprint: etago-04-stack-v1
produced_at: 2026-05-09
manual_only: false
verification_mode: real-network-smoke
---

# Phase 04 — Verification Commands (Q-D8 답: 실 네트워크 smoke)

## Verification Commands

```bash
# G1 — build smoke
cd D:/github/cf/etago
go build -o etago(.exe) ./cmd/etago
test -x ./etago || test -f ./etago.exe   # binary present

# G2 — unit + mock test (no network)
go test ./...

# G3 — live smoke (network 의무, Q-D8=1)
go test -tags=smoke ./tests/...

# G4 — CLI live smoke (5 pairs)
./etago "강남역" "수원시청"     && echo PASS-1 || echo FAIL-1
./etago "서울역" "인천공항"     && echo PASS-2 || echo FAIL-2
./etago "부산역" "해운대"       && echo PASS-3 || echo FAIL-3
./etago "광화문" "성수동"       && echo PASS-4 || echo FAIL-4
./etago "양재IC" "판교IC"       && echo PASS-5 || echo FAIL-5
```

## Acceptance Criteria mapping

| SC | 검증 |
|----|------|
| SC-1 (5쌍 ≥80%) | G4 PASS 카운트 ≥ 4/5 |
| SC-2 (±5분 정확) | 사용자 manual 비교 (페이즈 09 옵션) |
| SC-3 (exit code) | unit test (`internal/cli/exitcode_test.go`) |
| SC-4 (single binary) | G1 binary present |
| SC-5 (--help) | `./etago --help` exit 0 + "usage" 텍스트 |

## Manual 부속 (선택)

페이즈 09 게이트에서 manual 비교 5쌍 — 사용자가 직접 Naver Map 웹 UI 와 비교해 ±5분 일치 확인 (선택, blocking 아님).
