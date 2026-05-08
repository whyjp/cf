---
skill_name: shipoftheseus:theseus-orchestrator
skill_version: 0.9.38
phase: 04-stack
project_id: etago
fingerprint: etago-04-stack-v1
prev_fingerprint: etago-04-autonomy-v1
produced_at: 2026-05-09
---

# Phase 04 — 스택 합의

## 언어 / 컴파일러

- **Go 1.22+** (사용자 명시).
- toolchain pin: `go 1.22` (go.mod 의 directive). 1.21 이하는 unsupported (URL.JoinPath 등 사용).

## 패키지 매니저

- `go mod` (Go 표준).
- 외부 사설 proxy 없음 — `GOPROXY=https://proxy.golang.org,direct`.

## 의존성 정책 — *최소* (KISS)

| 의존 | 사용 의도 | default | 대안 |
|------|---------|---------|------|
| `net/http` (stdlib) | HTTP 호출 | ✅ stdlib | ❌ resty 등 X |
| `encoding/json` (stdlib) | JSON 파싱 | ✅ stdlib | — |
| `flag` (stdlib) | CLI args | ✅ stdlib | cobra 는 over-engineering |
| `context` (stdlib) | timeout cancel | ✅ stdlib | — |
| `golang.org/x/text/encoding` | 한글 인코딩 변환 | 필요 시만 | UTF-8 가정 — 보통 불필요 |

→ **0 third-party 의존 default**. 외부 라이브러리 추가 시 페이즈 06 plan 에 정당화 의무.

## 빌드

```bash
# Linux/macOS
go build -o etago ./cmd/etago

# Windows
go build -o etago.exe ./cmd/etago

# Cross-compile
GOOS=linux GOARCH=amd64 go build -o dist/etago-linux-amd64 ./cmd/etago
GOOS=darwin GOARCH=arm64 go build -o dist/etago-darwin-arm64 ./cmd/etago
GOOS=windows GOARCH=amd64 go build -o dist/etago-windows-amd64.exe ./cmd/etago
```

## 테스트

- `go test ./...` (stdlib `testing`).
- `httptest` (stdlib) 으로 mock 서버 — 단위 테스트.
- live smoke: `tests/smoke_test.go` build tag `//go:build smoke` — Phase 09 verification.
