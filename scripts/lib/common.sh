#!/usr/bin/env bash
# scripts/lib/common.sh -- log + pid helpers.

set -euo pipefail

log_info()  { echo "[$(date +%H:%M:%S)] [INFO]  $*" >&2; }
log_warn()  { echo "[$(date +%H:%M:%S)] [WARN]  $*" >&2; }
log_error() { echo "[$(date +%H:%M:%S)] [ERROR] $*" >&2; }

pid_alive() {
    local pid="$1"
    [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

write_pid() {
    local file="$1"
    local pid="$2"
    echo "$pid" > "$file"
}

read_pid() {
    local file="$1"
    [ -f "$file" ] || return 1
    cat "$file"
}

stop_pid_file() {
    local file="$1"
    local timeout="${2:-10}"
    local pid
    pid=$(read_pid "$file" 2>/dev/null || echo "")
    if [ -z "$pid" ]; then
        log_warn "no pid file: $file"
        return 0
    fi
    if ! pid_alive "$pid"; then
        log_warn "pid $pid not running"
        rm -f "$file"
        return 0
    fi
    log_info "SIGTERM $pid"
    kill -TERM "$pid"
    local i=0
    while [ $i -lt "$timeout" ] && pid_alive "$pid"; do
        sleep 1
        i=$((i + 1))
    done
    if pid_alive "$pid"; then
        log_warn "SIGKILL $pid"
        kill -KILL "$pid"
    fi
    rm -f "$file"
}
