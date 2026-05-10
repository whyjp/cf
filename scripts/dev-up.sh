#!/usr/bin/env bash
# Start be-api + be-for-fe in background. PIDs to .run/.
# SP-A unified dev launcher -- replaces older backend-up.sh single-service mode.
. "$(dirname "$0")/lib/env.sh"
. "$(dirname "$0")/lib/common.sh"

start_be_api() {
    if [ -f "$BE_API_PID_FILE" ] && pid_alive "$(cat "$BE_API_PID_FILE")"; then
        log_warn "be-api already running (pid $(cat "$BE_API_PID_FILE"))"
        return 0
    fi
    [ -f "$BE_API_PID_FILE" ] && rm -f "$BE_API_PID_FILE"
    log_info "starting be-api on $BE_API_HOST:$BE_API_PORT"
    cd "$REPO_ROOT"
    nohup "$UV" run --package cf-be-api uvicorn cf_be_api.api:app \
        --host "$BE_API_HOST" --port "$BE_API_PORT" \
        > "$BE_API_LOG_FILE" 2>&1 &
    write_pid "$BE_API_PID_FILE" "$!"
    log_info "be-api pid $! -- log: $BE_API_LOG_FILE"
}

start_bff() {
    if [ -f "$BFF_PID_FILE" ] && pid_alive "$(cat "$BFF_PID_FILE")"; then
        log_warn "bff already running (pid $(cat "$BFF_PID_FILE"))"
        return 0
    fi
    [ -f "$BFF_PID_FILE" ] && rm -f "$BFF_PID_FILE"
    log_info "starting be-for-fe on $BFF_HOST:$BFF_PORT (upstream http://${BE_API_HOST}:${BE_API_PORT})"
    cd "$REPO_ROOT"
    BFF_BE_API_BASE_URL="http://${BE_API_HOST}:${BE_API_PORT}" \
        nohup "$UV" run --package cf-be-for-fe uvicorn cf_be_for_fe.api:app \
        --host "$BFF_HOST" --port "$BFF_PORT" \
        > "$BFF_LOG_FILE" 2>&1 &
    write_pid "$BFF_PID_FILE" "$!"
    log_info "bff pid $! -- log: $BFF_LOG_FILE"
}

start_be_api
sleep 2
# healthz polling -- be-api
for i in 1 2 3 4 5 6 7 8 9 10; do
    if curl -sf "http://${BE_API_HOST}:${BE_API_PORT}/healthz" >/dev/null 2>&1; then
        log_info "be-api ready"
        break
    fi
    sleep 0.5
done

start_bff
# healthz polling -- bff (use 127.0.0.1 to dial when host is 0.0.0.0)
_bff_dial="${BFF_HOST}"
[ "$_bff_dial" = "0.0.0.0" ] && _bff_dial="127.0.0.1"
for i in 1 2 3 4 5 6 7 8 9 10; do
    if curl -sf "http://${_bff_dial}:${BFF_PORT}/healthz" >/dev/null 2>&1; then
        log_info "bff ready"
        break
    fi
    sleep 0.5
done

log_info "logs: $BE_API_LOG_FILE  $BFF_LOG_FILE"
