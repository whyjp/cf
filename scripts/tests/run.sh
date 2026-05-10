#!/usr/bin/env bash
. "$(dirname "$0")/../lib/env.sh"
. "$(dirname "$0")/../lib/common.sh"

cd "$(dirname "$0")"
fail=0
for t in test_*.sh; do
    log_info "=== $t ==="
    if ! bash "$t"; then
        log_error "$t FAILED"
        fail=1
    fi
done
[ $fail -eq 0 ] && { log_info "ALL ASSERTIONS PASS"; exit 0; } || exit 1
