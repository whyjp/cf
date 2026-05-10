#!/usr/bin/env bash
# Full pipeline: jsonl -> postgres -> falkor + etago geocode + lexicon/seed.
. "$(dirname "$0")/lib/env.sh"
. "$(dirname "$0")/lib/common.sh"

cd "$REPO_ROOT"
log_info "cf-pipeline full_run (args: $*)"
exec "$UV" run --package cf-pipeline python -m cf_pipeline.full_run \
    --camfit-data "$CAMFIT_DATA" \
    --txcp-data "$TXCP_DATA" \
    "$@"
