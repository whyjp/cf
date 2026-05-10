# cf be-api (Go)

The HTTP/JSON API consumed by the BFF (`be-for-fe`). Go rewrite of the
former Python `cf-be-api`. SP-D shipped 2026-05-11 (D-8 cutover).

## Run (live, port 8071)

```sh
cd backend/be-api
go build -o be-api.exe ./cmd/be-api
./be-api.exe
```

`scripts/dev-up.sh` builds + launches automatically and bundles mingw64
runtime DLLs (cgo dependency for ONNX). The verification port (8073) used
during D-1~D-7 is gone — be-api is now the canonical service on **8071**.

## Test

```sh
# Unit + helper tests (no live deps)
go test ./...

# Cross-validation suite (needs both Python :8071 + Go :8073 live)
go test -tags integration -count=1 ./tests/integration/... -v

# Frozen-fixture regression suite
go test -tags regression -count=1 ./tests/regression/... -v

# Performance bench (Python vs Go side-by-side)
./tests/perf/bench.sh > /tmp/perf.log
```

If the Windows AppLocker policy blocks test binaries from `%TEMP%`,
pre-build with `go test -c -o D:\path\you\trust\some.test.exe ./tests/...`
and invoke directly. See `docs/sp-d-performance-baseline.md` for the
recorded D-7 baseline.

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
- [x] D-2 domain + ports + adapters
- [x] D-3 embed (ONNX D-0 흡수) + semantic_search
- [x] D-4 read endpoints + camping_filter
- [x] D-5 etago absorption + /eta*
- [x] D-6 admin + graph
- [x] D-7 integration + perf bench
- [ ] D-8 cutover (Big bang)

## Build environment (Windows + CGO)

`onnxruntime_go` requires CGO. Setup once per dev machine:

1. **MSYS2 + mingw64 gcc** (only needed for builds that link the embedder;
   you can skip if running with `ONNXRUNTIME_LIB` unset, which disables
   `/sites/search` + `/admin/reembed` but leaves everything else working).

   ```powershell
   winget install MSYS2.MSYS2
   # In MSYS2 shell:
   pacman -S mingw-w64-x86_64-gcc
   ```

2. **Add `C:\msys64\mingw64\bin` to PATH** in whatever shell you build from
   (PowerShell or Git Bash). Verify:

   ```sh
   gcc --version   # → gcc.exe (Rev*, Built by MSYS2 project) 15.x
   ```

3. **Download Microsoft onnxruntime native lib** (v1.20.x verified):
   <https://github.com/microsoft/onnxruntime/releases> → unzip
   `onnxruntime-win-x64-1.20.1.zip`, copy `lib/onnxruntime.dll` somewhere
   stable.

   ⚠️ Windows ships a stripped-down `onnxruntime.dll` v1.17.1 in
   `C:\Windows\System32` (used by Edge/Copilot). If you set
   `ONNXRUNTIME_LIB=./onnxruntime.dll` (relative), Windows may load the
   System32 copy instead — its API version (17) is too old for
   `onnxruntime_go` v1.13.0 which requests API 20, and you'll see
   *"The requested API version [20] is not available, only API versions
   [1, 17] are supported"*. **Always pass an absolute path.**

4. **Set runtime env vars** (PowerShell example):

   ```powershell
   $env:ONNXRUNTIME_LIB        = "D:\github\cf-go\backend\be-api-go\onnxruntime.dll"
   $env:KO_SROBERTA_ONNX       = "D:\github\cf-go\backend\be-api-go\assets-onnx\ko-sroberta.onnx"
   $env:KO_SROBERTA_TOKENIZER  = "D:\github\cf-go\backend\be-api-go\assets-onnx\tokenizer.json"
   $env:DATABASE_URL           = "postgresql://camfit:camfit@localhost:5432/camfit"
   $env:FALKORDB_URL           = "redis://localhost:6379"
   $env:BE_API_PORT            = "8073"
   go run ./cmd/be-api
   ```

5. **Optional ETA credentials** — Naver Cloud Platform (Maps Directions 5)
   and Kakao K1. Both empty → `/eta` falls back to anonymous Naver search +
   Kakao K1 + OSRM (still works, just lower-quality):

   ```powershell
   $env:NAVER_NCP_CLIENT_ID     = "..."
   $env:NAVER_NCP_CLIENT_SECRET = "..."
   $env:KAKAO_REST_KEY          = "..."
   ```

If `ONNXRUNTIME_LIB` / model / tokenizer paths are NOT set, the embedder is
nil — `/sites/search`, `/sites/{id}/similar`, and `/admin/reembed` return
503; everything else works. Keep this in mind when running without CGO/ONNX
on a CI runner.

## Toolchain notes

- Built with Go 1.26 on Windows (`C:\Program Files\Go\bin\go.exe`); module declares `go 1.25` for floor compatibility.
- WSL `bash` does not expose `go.exe`; run `go` from PowerShell or prepend `C:\Program Files\Go\bin` to PATH when shelling from Git Bash.
- The falkor smoke script (`scripts/falkor-go-smoke.sh`) is bash; on Windows, invoke via Git Bash with Go in PATH.
