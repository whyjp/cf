---
skill_name: shipoftheseus:theseus-orchestrator
skill_version: 0.9.38
phase: 06-plan-universe-2
project_id: etago
fingerprint: etago-u2-plan-v1
prev_fingerprint: etago-u2-meta-v1
produced_at: 2026-05-09
universe_id: 2
---

# Plan — Universe 2 (Concurrent Race)

## 1. 파일 경로

U1 과 동일 + `internal/route/race.go`. 9 파일.

## 2. 다이어그램 + 인터페이스

### sequenceDiagram (race)

```mermaid
sequenceDiagram
    participant CLI
    participant R as race
    participant N as Naver
    participant K as Kakao
    par
        R->>N: Lookup(ctx)
    and
        R->>K: Lookup(ctx)
    end
    N-->>R: result/err (먼저 도착)
    R->>K: cancel ctx
    R-->>CLI: Duration{Source: which-won}
```

### graph (use-case)

```mermaid
graph LR
    U[User] --> CLI
    CLI --> RACE[race.go]
    RACE -->|go| N[Naver]
    RACE -->|go| K[Kakao]
    N --> WIN[first success]
    K --> WIN
    WIN --> OUT
```

### 인터페이스

```go
type RaceResult struct {
    Duration
    LatencyMs int
}
func RaceProviders(ctx context.Context, in NormalizedInput, providers ...Provider) (RaceResult, error)
type Provider interface { Name() string; Lookup(ctx, in) (Duration, error) }
```

## 3. TODO DAG

T-001~T-006 = U1, + T-005a `route/race.go` 동시성 orchestrator.

## 4. 모듈 sequenceDiagram (모듈수만큼)

`parse`, `route/naver`, `route/kakao`, `route/race`, `duration` — 5개 (U1 의 4개 + race).

## 5. Data Structure Invariants

| Struct | Invariant |
|--------|----------|
| RaceResult | LatencyMs ≥ 0, Source ∈ providers |
| ctx cancellation | 첫 성공 즉시 cancel |

## 6. Test Surface

`TestRace_naverFasterThanKakao_naverWins`, `TestRace_kakaoFasterThanNaver_kakaoWins`, `TestRace_bothFail_returnsAggregate`.

## 7. Error Handling

둘 다 실패 → aggregate error (둘 다 stderr).

## 8. Implementation Guidance

```go
func RaceProviders(ctx, in, ps...) (RaceResult, error) {
    rctx, cancel := context.WithTimeout(ctx, 6*time.Second)
    defer cancel()
    type r struct{ d Duration; err error; ms int }
    ch := make(chan r, len(ps))
    start := time.Now()
    for _, p := range ps {
        go func(p Provider) {
            d, err := p.Lookup(rctx, in)
            ch <- r{d, err, int(time.Since(start).Milliseconds())}
        }(p)
    }
    var errs []error
    for range ps {
        x := <-ch
        if x.err == nil { return RaceResult{x.d, x.ms}, nil }
        errs = append(errs, x.err)
    }
    return RaceResult{}, fmt.Errorf("all failed: %v", errs)
}
```
