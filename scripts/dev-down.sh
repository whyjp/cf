#!/usr/bin/env bash
# Stop be-for-fe + be-api launched via dev-up.sh.
. "$(dirname "$0")/lib/env.sh"
. "$(dirname "$0")/lib/common.sh"

stop() {
    local pid_file="$1"
    local name="$2"
    if [ ! -f "$pid_file" ]; then
        log_info "$name not running"
        return 0
    fi
    local pid
    pid=$(cat "$pid_file")
    if pid_alive "$pid"; then
        log_info "stopping $name (pid $pid)"
        kill "$pid" 2>/dev/null || true
        for _ in 1 2 3 4 5; do
            pid_alive "$pid" || break
            sleep 0.5
        done
        pid_alive "$pid" && kill -9 "$pid" 2>/dev/null || true
    else
        log_warn "$name pid $pid not running -- removing stale pid file"
    fi
    rm -f "$pid_file"
}

# Stop bff first so we don't see upstream-down errors during teardown.
stop "$BFF_PID_FILE" "bff"
stop "$BE_API_PID_FILE" "be-api"
