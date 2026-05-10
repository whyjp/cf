#!/usr/bin/env bash
. "$(dirname "$0")/lib/env.sh"
. "$(dirname "$0")/lib/common.sh"

echo "=== DB ==="
"$REPO_ROOT/scripts/db-status.sh" || true
echo ""
echo "=== Backend ==="
if [ -f "$BACKEND_PID_FILE" ]; then
    pid=$(cat "$BACKEND_PID_FILE")
    if pid_alive "$pid"; then
        echo "backend pid $pid alive (port $BACKEND_PORT)"
    else
        echo "backend pid file stale ($pid not alive)"
    fi
else
    echo "backend not running"
fi
echo ""
echo "=== Last 10 backend log lines ==="
tail -n 10 "$BACKEND_LOG_FILE" 2>/dev/null || echo "(no log)"
