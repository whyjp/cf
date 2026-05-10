#!/usr/bin/env bash
# Start uvicorn in background. PID -> .run/backend.pid. Log -> .run/backend.log.
. "$(dirname "$0")/lib/env.sh"
. "$(dirname "$0")/lib/common.sh"

if [ -f "$BACKEND_PID_FILE" ]; then
    pid=$(cat "$BACKEND_PID_FILE")
    if pid_alive "$pid"; then
        log_warn "backend already running (pid $pid)"
        exit 0
    fi
    log_warn "stale pid file -- removing"
    rm -f "$BACKEND_PID_FILE"
fi

log_info "starting uvicorn cf_backend.api:app on $BACKEND_HOST:$BACKEND_PORT"
cd "$REPO_ROOT"
nohup "$UV" run --package cf-backend uvicorn cf_backend.api:app \
    --host "$BACKEND_HOST" --port "$BACKEND_PORT" \
    > "$BACKEND_LOG_FILE" 2>&1 &
write_pid "$BACKEND_PID_FILE" "$!"
log_info "backend pid $! -- log: $BACKEND_LOG_FILE"
