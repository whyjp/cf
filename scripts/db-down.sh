#!/usr/bin/env bash
. "$(dirname "$0")/lib/env.sh"
. "$(dirname "$0")/lib/common.sh"

cd "$REPO_ROOT/docker"
log_info "docker compose down (volumes preserved)"
docker compose down
