#!/usr/bin/env bash
# DEPRECATED single-service launcher.
# SP-A: prefer scripts/dev-up.sh (boots be-api + be-for-fe together).
# This script now boots only be-for-fe (BFF) and requires be-api to be up already.
. "$(dirname "$0")/lib/env.sh"
. "$(dirname "$0")/lib/common.sh"

log_warn "backend-up.sh: SP-A 이후로는 dev-up.sh 권장 (be-api + bff 동시 부팅)"
log_warn "이 스크립트는 BFF 만 띄움. be-api 가 먼저 떠 있어야 함."

if [ ! -f "$BE_API_PID_FILE" ] || ! pid_alive "$(cat "$BE_API_PID_FILE")"; then
    log_error "be-api 가 떠있지 않음. dev-up.sh 사용 권장 (be-api + bff 동시 부팅)"
    exit 1
fi

if [ -f "$BFF_PID_FILE" ] && pid_alive "$(cat "$BFF_PID_FILE")"; then
    log_warn "bff already running (pid $(cat "$BFF_PID_FILE"))"
    exit 0
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
