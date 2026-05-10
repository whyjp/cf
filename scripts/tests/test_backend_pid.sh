#!/usr/bin/env bash
set -euo pipefail
. "$(dirname "$0")/../lib/common.sh"

# write_pid + read_pid roundtrip
tmp=$(mktemp)
write_pid "$tmp" "12345"
got=$(read_pid "$tmp")
[ "$got" = "12345" ] || { echo "FAIL: write_pid/read_pid roundtrip"; exit 1; }
rm -f "$tmp"

# pid_alive of bogus pid
if pid_alive "999999999"; then
    echo "FAIL: pid_alive returned true for bogus pid"
    exit 1
fi
echo "pid helpers OK"
