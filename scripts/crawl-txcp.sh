#!/usr/bin/env bash
# Pull txcp (thankqcamping) camping list. Args passthrough.
. "$(dirname "$0")/lib/env.sh"
. "$(dirname "$0")/lib/common.sh"

cd "$REPO_ROOT"
log_info "txcp-crawl pull (args: $*)"
exec "$UV" run --package txcp-crawl python -m txcp_crawl.cli pull "$@"
