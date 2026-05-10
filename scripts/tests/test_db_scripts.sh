#!/usr/bin/env bash
# Verify db-*.sh files are syntactically valid bash.
set -euo pipefail
. "$(dirname "$0")/../lib/env.sh"

for f in db-up.sh db-down.sh db-status.sh; do
    bash -n "$REPO_ROOT/scripts/$f" || { echo "SYNTAX FAIL: $f"; exit 1; }
done
echo "db-* scripts syntactically valid"
