# cf be-api-go

Go rewrite of `cf-be-api` (Python). SP-D in progress (worktree: `D:/github/cf-go`, branch base: `feature/sp-d-go-rewrite`).

## Run (D-1~D-7 verification mode, port 8073)

```sh
cd backend/be-api-go
go run ./cmd/be-api
```

The Go service binds **8073** during the SP-D verification window so it can run side-by-side with the legacy Python `be-api` on 8072. After D-8 cutover the port flips to 8072.

## Test

```sh
go test ./...
```

## Architecture

- Spec: `docs/superpowers/specs/2026-05-10-sp-d-go-rewrite-design.md`
- Plan: `docs/superpowers/plans/2026-05-10-sp-d-go-rewrite.md`

## D-1 decisions

- HTTP router: **chi v5** (`github.com/go-chi/chi/v5`)
- Settings: **envconfig** (`github.com/kelseyhightower/envconfig`)
- Logging: **`log/slog`** (stdlib)
- FalkorDB Go client: **`github.com/FalkorDB/falkordb-go`** (smoke PASS — see `scripts/falkor-go-smoke.sh`)
  - v0.1.0 `Query` signature is 3-arg: `Query(query string, params map[string]interface{}, options *QueryOptions)` — pass `nil, nil` for unparameterised reads.
  - `ConnectionOption` is an alias for `redis.Options`; only `Addr` is required.
  - D-2 falkor adapter uses this client. RESP-via-`go-redis` fallback is **not** required.

## Status

- [x] D-0 ONNX PoC (gate PASSED)
- [x] D-1 skeleton + healthz + falkor smoke
- [ ] D-2 domain + ports + adapters
- [ ] D-3 embed (ONNX D-0 흡수) + semantic_search
- [ ] D-4 read endpoints + camping_filter
- [ ] D-5 etago absorption + /eta*
- [ ] D-6 admin + graph
- [ ] D-7 integration + perf bench
- [ ] D-8 cutover (Big bang)

## Toolchain notes

- Built with Go 1.26 on Windows (`C:\Program Files\Go\bin\go.exe`); module declares `go 1.22` for floor compatibility.
- WSL `bash` does not expose `go.exe`; run `go` from PowerShell or prepend `C:\Program Files\Go\bin` to PATH when shelling from Git Bash.
- The falkor smoke script (`scripts/falkor-go-smoke.sh`) is bash; on Windows, invoke via Git Bash with Go in PATH.
