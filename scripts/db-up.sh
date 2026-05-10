#!/usr/bin/env bash
# Bring up postgres + falkordb via docker compose. Idempotent.
. "$(dirname "$0")/lib/env.sh"
. "$(dirname "$0")/lib/common.sh"

cd "$REPO_ROOT/docker"
log_info "docker compose up -d"
docker compose up -d

log_info "waiting for healthchecks (<=60s)"
for i in $(seq 1 60); do
    falkor_h=$(docker compose ps --format json 2>/dev/null | grep -c '"Health":"healthy"' || echo "0")
    if [ "$falkor_h" -ge "2" ]; then
        log_info "both healthy after ${i}s"
        exit 0
    fi
    sleep 1
done
log_error "timeout waiting for healthchecks"
docker compose ps
exit 1
