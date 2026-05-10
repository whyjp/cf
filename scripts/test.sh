#!/usr/bin/env bash
# Run pytest "not live" across all 4 packages.
. "$(dirname "$0")/lib/env.sh"
. "$(dirname "$0")/lib/common.sh"

cd "$REPO_ROOT"
fail=0
for pkg in txcp-crawl camfit-crawl cf-be-api cf-pipeline; do
    log_info "=== $pkg ==="
    case "$pkg" in
        txcp-crawl)    path=crawl/txcp ;;
        camfit-crawl)  path=crawl/camfit ;;
        cf-be-api)     path=backend/be-api ;;
        cf-pipeline)   path=pipeline ;;
    esac
    if ! "$UV" run --package "$pkg" pytest "$path" -m "not live and not integration" --tb=short 2>&1 | tail -5; then
        fail=1
    fi
done
[ $fail -eq 0 ] && log_info "ALL PASS" || { log_error "SOME FAILED"; exit 1; }
