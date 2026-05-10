#!/usr/bin/env bash
# Pull camfit camping list. Args passthrough.
. "$(dirname "$0")/lib/env.sh"
. "$(dirname "$0")/lib/common.sh"

cd "$REPO_ROOT"
log_info "camfit-crawl (args: $*)"
exec "$UV" run --package camfit-crawl python -m camfit_crawl.cli "$@"
