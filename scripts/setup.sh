#!/usr/bin/env bash
# One-shot dev setup: uv sync + db-up + backend-up.
. "$(dirname "$0")/lib/env.sh"
. "$(dirname "$0")/lib/common.sh"

cd "$REPO_ROOT"
log_info "uv sync --all-packages --all-extras"
"$UV" sync --all-packages --all-extras
"$REPO_ROOT/scripts/db-up.sh"
"$REPO_ROOT/scripts/backend-up.sh"
log_info "setup complete"
