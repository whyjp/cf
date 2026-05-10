#!/usr/bin/env bash
# Run pytest "not live" across all packages -- backend split: cf-be-api + cf-be-for-fe.
. "$(dirname "$0")/lib/env.sh"
. "$(dirname "$0")/lib/common.sh"

cd "$REPO_ROOT"
fail=0
for pkg in txcp-crawl camfit-crawl cf-be-api cf-be-for-fe cf-pipeline; do
    log_info "=== $pkg ==="
    # crawl/{txcp,camfit} need --extra dev for pytest-asyncio + respx; backend pkgs already resolve them.
    extras=()
    case "$pkg" in
        txcp-crawl)    path=crawl/txcp ;          extras=(--extra dev) ;;
        camfit-crawl)  path=crawl/camfit ;        extras=(--extra dev) ;;
        cf-be-api)     path=backend/be-api/tests ;;
        cf-be-for-fe)  path=backend/be-for-fe/tests ;;
        cf-pipeline)   path=pipeline ;;
    esac
    if ! "$UV" run --package "$pkg" "${extras[@]}" pytest "$path" -m "not live and not integration" --tb=short 2>&1 | tail -5; then
        fail=1
    fi
done
[ $fail -eq 0 ] && log_info "ALL PASS" || { log_error "SOME FAILED"; exit 1; }
