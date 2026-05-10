#!/usr/bin/env bash
. "$(dirname "$0")/lib/env.sh"
. "$(dirname "$0")/lib/common.sh"

stop_pid_file "$BACKEND_PID_FILE" 10
log_info "backend stopped"
