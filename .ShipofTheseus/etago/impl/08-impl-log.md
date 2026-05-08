---
skill_name: shipoftheseus:theseus-orchestrator
skill_version: 0.9.38
phase: 08-impl-log
project_id: etago
fingerprint: etago-08-impl-v1
prev_fingerprint: etago-impl-dacapo-flow-v1
produced_at: 2026-05-09
---

# Implementation Log — etago

canonical 산출물 (`D:/github/cf/etago/`) 에 대한 페이즈 06 plan TODO ID 매핑 + 모듈명 + 인터페이스 노출. HR9.b 의무 충족 (TODO ID 매핑 ≥ 3 / 모듈명 / 인터페이스).

## TODO ID 매핑 (T-001 ~ T-009)

| TODO ID | 모듈 | 파일 (절대) | 인터페이스 / 함수 노출 | 상태 |
|---------|------|------------|---------------------|------|
| T-001 | (전역) | `etago/go.mod` | `module github.com/whyjp/etago / go 1.22` | ✅ |
| T-002 | parse | `etago/internal/parse/input.go` | `NormalizeInputs(start,end string) (NormalizedInput, error)` + sentinel `ErrEmpty / ErrCoordNotAllowed / ErrTooLong` | ✅ |
| T-003 | route (Naver) | `etago/internal/route/naver.go` | `NewNaverProvider(client, ua) *NaverProvider` + Provider conformant | ✅ |
| T-004 | route (Kakao) | `etago/internal/route/kakao.go` | `NewKakaoProvider(client, ua) *KakaoProvider` + Provider conformant | ✅ |
| T-005 | route (orchestration) | `etago/internal/route/route.go` + `provider.go` | `Provider` interface + `Duration` struct + `GetDuration(ctx, in, providers) (Duration, error)` + sentinel 5종 | ✅ |
| T-006 | duration | `etago/internal/duration/format.go` | `Format(d, in, opts) string` + `Options{JSON bool}` | ✅ |
| T-007 | cmd | `etago/cmd/etago/main.go` | `main()` + `run(argv, stdout, stderr) int` + `buildProviders(source, ua, client) ([]Provider, error)` + `printUsage(w)` | ✅ |
| T-008 | tests | `etago/tests/smoke_test.go` | `TestSmoke_5pairs_majorityPass` (build tag `smoke`) + `skipIfOffline` | ✅ |
| T-009 | docs | `etago/README.md` | quickstart + Windows hint + exit code 표 | ✅ |

## 단위 테스트 노출 (≥ 27)

| 파일 | 테스트 |
|------|--------|
| `internal/parse/input_test.go` | 7 (empty, whitespace, coord, UTF-8 보존, trim, over-length, korean variants) |
| `internal/route/route_test.go` | 7 (naver wins, fallback, input rejected, empty path, both fail, timeout, no providers) |
| `internal/route/naver_test.go` | 7 (Provider conformance, mock duration, 5xx, 4xx, empty schema, totalTime sec, helpers) |
| `internal/route/kakao_test.go` | 4 (Provider conformance, mock, 5xx, helpers) |
| `internal/duration/format_test.go` | 3 (default, json, zero) |
| `cmd/etago/main_test.go` | 5 (Usage, buildProviders auto/naver/kakao/unknown) |

총 33 단위 + 1 smoke (= 34 테스트 signature). plan §6 test surface mapping 12 항 모두 매칭.

## 인터페이스 표면 (export 노출)

```go
// internal/parse
type NormalizedInput struct { Start, End string }
const MaxRunes = 256
var ErrEmpty, ErrCoordNotAllowed, ErrTooLong error
func NormalizeInputs(start, end string) (NormalizedInput, error)

// internal/route
type Duration struct { Min int; Source string; LatencyMs int }
type Provider interface { Name() string; Lookup(ctx, NormalizedInput) (Duration, error) }
const PerSourceTimeout = 6 * time.Second
var ErrEmptyPath, ErrInputRejected, ErrUpstreamFail, ErrAllSourcesFail, ErrParseSchema error
func GetDuration(ctx, in, providers) (Duration, error)
type NaverProvider struct{...}
type KakaoProvider struct{...}
func NewNaverProvider(client, ua) *NaverProvider
func NewKakaoProvider(client, ua) *KakaoProvider

// internal/duration
type Options struct { JSON bool }
func Format(d, in, opts) string

// cmd/etago (internal)
func run(argv, stdout, stderr) int
func buildProviders(source, ua, client) ([]Provider, error)
func main()
```

## 페이즈 06 plan 8 항목 → impl 매핑

| plan §  | 의무 | impl 산출 |
|---------|------|----------|
| §1 파일 ≥ 5 | 9 파일 | 9 source + 6 test = 15 ✅ |
| §2 다이어그램 + 인터페이스 ≥ 3 | sequenceDiagram 5 + graph 1 + 인터페이스 4 | impl 코드 = plan 인터페이스 정의 1:1 ✅ |
| §3 TODO DAG | T-001~T-009 | 모두 완료 (위 표) ✅ |
| §4 모듈 의존 다이어그램 | 4 모듈 | 모듈 분리 일치 ✅ |
| §5 DS invariants | 3 struct × 4 항 | 코드 주석 + test 단언 ✅ |
| §6 Test surface mapping | 12 항 | 33 unit ≥ 12 ✅ |
| §7 Error handling / fallback | 10 케이스 | 7 sentinel + route.go 처리 ✅ |
| §8 Implementation guidance per TODO | 9 TODO | impl 모두 plan guidance 따름 ✅ |

## Go 미설치 환경 운영 결정

본 환경 (Windows + WSL/PowerShell) 에 `go` 명령 부재. 본 페이즈는 *코드 작성* 으로 정의 (페이즈 08 의무). *컴파일 검증* 은 페이즈 09 게이트의 일부 — 사용자 또는 CI 가 `go install` 후 `go build ./cmd/etago` 실행 의무. 현재 페이즈 09 는 `entry_blocked: false` (Q-D9 답 4) 로, *manual smoke* 부분 강등으로 진입.

코드는 syntax-correct 의무 — 작성자 (impl-er) 가 Go 1.22 의 `net/http`, `encoding/json`, `regexp`, `unicode/utf8` 표준 패키지의 시그니처에 맞춰 작성. 사용자 빌드 시 0-error 기대.
