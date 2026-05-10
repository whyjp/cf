#!/usr/bin/env bash
. "$(dirname "$0")/lib/env.sh"
. "$(dirname "$0")/lib/common.sh"

"$REPO_ROOT/scripts/backend-down.sh"
"$REPO_ROOT/scripts/db-down.sh"
log_info "teardown complete"
