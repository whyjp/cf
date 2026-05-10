#!/usr/bin/env bash
set -euo pipefail
. "$(dirname "$0")/../lib/env.sh"

cd "$REPO_ROOT"
output=$("$UV" run --package cf-pipeline python -m cf_pipeline.full_run --dry-run 2>&1)
echo "$output" | grep -q "ingest_camps" || { echo "FAIL: ingest_camps missing"; exit 1; }
echo "$output" | grep -q "DRY RUN" || { echo "FAIL: DRY RUN marker missing"; exit 1; }
echo "migrate dry-run OK"
