#!/usr/bin/env bash
# Run unit + non-live tests across all packages.
# SP-D D-8 cutover (2026-05-11): be-api: Go (`go test ./...`).
# SP-D D-9 cutover (2026-05-11): cf-be-api-py distribution dropped — its
# Python core (cf_be_api package) is now shipped inside cf-pipeline, so the
# legacy library tests run under `--package cf-pipeline` (pyproject testpaths
# covers tests/ + tests-be-api-legacy/).
. "$(dirname "$0")/lib/env.sh"
. "$(dirname "$0")/lib/common.sh"

cd "$REPO_ROOT"
fail=0

# ── Go ─────────────────────────────────────────────────────────────────
# CC=gcc.exe + WSLENV PATH/l → see scripts/dev-up.sh build_be_api comments.
log_info "=== be-api (Go) ==="
if ! ( cd "$REPO_ROOT/backend/be-api" && \
       WSLENV="CGO_ENABLED:CC:CXX:PATH/l:${WSLENV:-}" \
       PATH="${MINGW64_BIN:-/c/msys64/mingw64/bin}:$PATH" \
       CGO_ENABLED=1 CC=gcc.exe CXX=g++.exe \
       "${GO_BIN:-go}" test ./... 2>&1 | tail -20 ); then
    fail=1
fi

# ── Python (uv workspace) ──────────────────────────────────────────────
for pkg in txcp-crawl camfit-crawl cf-be-for-fe cf-pipeline; do
    log_info "=== $pkg ==="
    extras=()
    case "$pkg" in
        txcp-crawl)    path=crawl/txcp ;          extras=(--extra dev) ;;
        camfit-crawl)  path=crawl/camfit ;        extras=(--extra dev) ;;
        cf-be-for-fe)  path=backend/be-for-fe/tests ;;
        cf-pipeline)   path=pipeline ;            extras=(--extra dev) ;;
    esac
    if ! "$UV" run --package "$pkg" "${extras[@]}" pytest "$path" -m "not live and not integration" --tb=short 2>&1 | tail -5; then
        fail=1
    fi
done
[ $fail -eq 0 ] && log_info "ALL PASS" || { log_error "SOME FAILED"; exit 1; }
